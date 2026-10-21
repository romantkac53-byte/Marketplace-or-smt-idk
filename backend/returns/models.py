from datetime import timedelta

from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from delivery.models import Delivery
from orders.models import OrderError, OrderItem, SellerOrder
from users.models import User
from warehouse.models import StockMovement, move_stock

RETURN_DAYS = 14  # срок, в течение которого после получения можно оформить возврат


class ReturnError(OrderError):
    """Ошибка возврата: истёк срок, товар не получен, недопустимый переход и т.п."""


class ReturnRequest(models.Model):
    """Заявка покупателя на возврат полученного товара."""

    class Reason(models.TextChoices):
        DEFECT = 'defect', 'Брак'
        WRONG_ITEM = 'wrong_item', 'Привезли не тот товар'
        NOT_FIT = 'not_fit', 'Не подошёл'
        OTHER = 'other', 'Другое'

    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Заявка подана'
        APPROVED = 'approved', 'Одобрена, ждём товар'
        COMPLETED = 'completed', 'Товар принят, деньги возвращены'
        REJECTED = 'rejected', 'Отклонена'
        CANCELLED = 'cancelled', 'Отменена покупателем'

    TRANSITIONS = {
        Status.REQUESTED: [Status.APPROVED, Status.REJECTED, Status.CANCELLED],
        Status.APPROVED: [Status.COMPLETED, Status.REJECTED],
        Status.COMPLETED: [],
        Status.REJECTED: [],
        Status.CANCELLED: [],
    }
    # Заявки, которые «занимают» количество: по ним товар уже возвращён или может быть возвращён
    ACTIVE_STATUSES = [Status.REQUESTED, Status.APPROVED, Status.COMPLETED]

    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name='returns',
                                   verbose_name='Позиция заказа')
    quantity = models.PositiveIntegerField('Количество', validators=[MinValueValidator(1)])
    reason = models.CharField('Причина', max_length=20, choices=Reason.choices)
    description = models.TextField('Описание проблемы', blank=True)
    status = models.CharField('Статус', max_length=20, choices=Status.choices, default=Status.REQUESTED)
    # Комментарий менеджера: причина отказа или заметки по приёмке. Видит покупатель
    manager_comment = models.CharField('Комментарий менеджера', max_length=255, blank=True)
    refund_amount = models.DecimalField('Возвращено денег', max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Возврат'
        verbose_name_plural = 'Возвраты'
        ordering = ['-created_at']

    def __str__(self):
        return f'Возврат №{self.pk}: {self.order_item.product_name} × {self.quantity}'

    @property
    def customer(self):
        return self.order_item.seller_order.order.customer

    @property
    def amount(self):
        """Сколько вернуть: по цене, за которую товар купили."""
        return self.order_item.price * self.quantity

    def _set_status(self, new_status, changed_by=None, comment='', extra_fields=()):
        if new_status not in self.TRANSITIONS[self.status]:
            raise ReturnError(
                f'Нельзя перевести возврат из «{self.get_status_display()}» '
                f'в «{self.Status(new_status).label}»'
            )
        old_status = self.status
        self.status = new_status
        self.save(update_fields=['status', *extra_fields])
        ReturnHistory.objects.create(return_request=self, old_status=old_status, new_status=new_status,
                                     changed_by=changed_by, comment=comment)

    def approve(self, changed_by=None):
        self._set_status(self.Status.APPROVED, changed_by, self.manager_comment)

    def reject(self, changed_by=None):
        if not self.manager_comment:
            raise ReturnError('Укажите причину отказа в поле «Комментарий менеджера»')
        self._set_status(self.Status.REJECTED, changed_by, self.manager_comment)

    def cancel(self, changed_by=None):
        """Покупатель передумал — пока заявку не рассмотрели."""
        self._set_status(self.Status.CANCELLED, changed_by)

    @transaction.atomic
    def complete(self, changed_by=None):
        """Склад принял товар: возврат на склад (брак — сразу списывается), деньги — на баланс."""
        # Проверяем статус ДО движения товара и денег
        if self.Status.COMPLETED not in self.TRANSITIONS[self.status]:
            raise ReturnError(f'Принять можно только одобренный возврат, сейчас: «{self.get_status_display()}»')
        product = self.order_item.product
        seller_order = self.order_item.seller_order
        move_stock(product, StockMovement.Type.RETURN, self.quantity, seller_order=seller_order,
                   created_by=changed_by, comment=str(self))
        if self.reason == self.Reason.DEFECT:
            move_stock(product, StockMovement.Type.WRITE_OFF, self.quantity, seller_order=seller_order,
                       created_by=changed_by, comment=f'Брак по возврату №{self.pk}')

        payment = seller_order.order.get_payment()
        if payment is not None:
            self.refund_amount = payment.refund(self.amount, changed_by, str(self))  # сколько реально вернули

        self._set_status(self.Status.COMPLETED, changed_by,
                         f'Возвращено {self.refund_amount} ₽', ['refund_amount'])


class ReturnHistory(models.Model):
    """История статусов возврата (требование ТЗ)."""

    return_request = models.ForeignKey(ReturnRequest, verbose_name='Возврат', on_delete=models.CASCADE, related_name='history')
    old_status = models.CharField('Прежний статус', max_length=20, blank=True)
    new_status = models.CharField('Новый статус', max_length=20)
    changed_by = models.ForeignKey(User, verbose_name='Кто изменил', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    changed_at = models.DateTimeField('Когда', auto_now_add=True)
    comment = models.CharField('Комментарий', max_length=255, blank=True)

    class Meta:
        verbose_name = 'Изменение статуса возврата'
        verbose_name_plural = 'История возврата'
        ordering = ['changed_at']

    def __str__(self):
        return f'{self.return_request}: {self.old_status or "—"} → {self.new_status}'


def returnable_quantity(order_item):
    """Сколько единиц позиции ещё можно вернуть (купленное минус уже заявленное)."""
    taken = order_item.returns.filter(status__in=ReturnRequest.ACTIVE_STATUSES) \
        .aggregate(total=Sum('quantity'))['total'] or 0
    return order_item.quantity - taken


def return_deadline(seller_order):
    """До какого момента можно оформить возврат (None — товар ещё не получен)."""
    if seller_order.status != SellerOrder.Status.DELIVERED:
        return None
    delivery = Delivery.objects.filter(seller_order=seller_order).first()  # свежие данные из базы
    received_at = delivery.delivered_at if delivery and delivery.delivered_at else seller_order.updated_at
    return received_at + timedelta(days=RETURN_DAYS)


def returnable_now(order_item):
    """Сколько штук можно вернуть прямо сейчас (0 — не получен, срок истёк или всё уже заявлено)."""
    deadline = return_deadline(order_item.seller_order)
    if deadline is None or timezone.now() > deadline:
        return 0
    return returnable_quantity(order_item)


@transaction.atomic
def request_return(customer, order_item, quantity, reason, description=''):
    """Покупатель оформляет заявку на возврат."""
    # Перечитываем позицию с подзаказом из базы и блокируем её:
    # статус подзаказа в памяти мог устареть, а две одновременные заявки не должны превысить купленное
    order_item = OrderItem.objects.select_for_update().select_related('seller_order__order').get(pk=order_item.pk)
    seller_order = order_item.seller_order
    if seller_order.order.customer_id != customer.pk:
        raise ReturnError('Это не ваш заказ')
    deadline = return_deadline(seller_order)
    if deadline is None:
        raise ReturnError('Вернуть можно только полученный товар')
    if timezone.now() > deadline:
        raise ReturnError(f'Срок возврата истёк: товар можно вернуть в течение {RETURN_DAYS} дней после получения')

    available = returnable_quantity(order_item)
    if not 1 <= quantity <= available:
        raise ReturnError(f'Можно вернуть от 1 до {available} шт.')

    return_request = ReturnRequest.objects.create(order_item=order_item, quantity=quantity,
                                                  reason=reason, description=description)
    ReturnHistory.objects.create(return_request=return_request, new_status=return_request.status,
                                 changed_by=customer.user, comment='Заявка подана')
    return return_request
