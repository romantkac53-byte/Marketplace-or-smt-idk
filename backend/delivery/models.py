import secrets
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone

from orders.models import Order, OrderError, SellerOrder
from users.models import User


class DeliveryError(OrderError):
    """Ошибка доставки: недопустимый переход, неверный код получения и т.п."""


class PickupPoint(models.Model):
    """Пункт выдачи заказов (ПВЗ)."""

    name = models.CharField('Название', max_length=100)
    city = models.CharField('Город', max_length=100)
    address = models.CharField('Адрес', max_length=255)
    working_hours = models.CharField('Часы работы', max_length=100, blank=True)
    storage_days = models.PositiveIntegerField('Срок хранения, дней', default=7)
    is_active = models.BooleanField('Работает', default=True)
    employees = models.ManyToManyField(
        User, blank=True, related_name='pickup_points', verbose_name='Сотрудники',
        limit_choices_to={'role': User.Role.PICKUP},
    )

    class Meta:
        verbose_name = 'Пункт выдачи'
        verbose_name_plural = 'Пункты выдачи'
        ordering = ['city', 'name']

    def __str__(self):
        return f'{self.name} ({self.city}, {self.address})'


class Delivery(models.Model):
    """Доставка одного подзаказа. Создаётся автоматически, когда склад собрал подзаказ."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает курьера'
        ASSIGNED = 'assigned', 'Курьер назначен'
        IN_TRANSIT = 'in_transit', 'В пути'
        AT_PICKUP_POINT = 'at_pickup_point', 'Ожидает в пункте выдачи'
        DELIVERED = 'delivered', 'Получен'
        RETURNED = 'returned', 'Не получен, возвращён'
        CANCELLED = 'cancelled', 'Отменена'

    TRANSITIONS = {
        Status.PENDING: [Status.ASSIGNED, Status.CANCELLED],
        Status.ASSIGNED: [Status.ASSIGNED, Status.IN_TRANSIT, Status.CANCELLED],  # ASSIGNED → ASSIGNED: смена курьера
        Status.IN_TRANSIT: [Status.DELIVERED, Status.AT_PICKUP_POINT, Status.RETURNED],
        Status.AT_PICKUP_POINT: [Status.DELIVERED, Status.RETURNED],
        Status.DELIVERED: [],
        Status.RETURNED: [],
        Status.CANCELLED: [],
    }
    FINAL_STATUSES = [Status.DELIVERED, Status.RETURNED, Status.CANCELLED]

    seller_order = models.OneToOneField(SellerOrder, verbose_name='Подзаказ', on_delete=models.CASCADE, related_name='delivery')
    courier = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name='deliveries',
        verbose_name='Курьер', limit_choices_to={'role': User.Role.COURIER},
    )
    status = models.CharField('Статус', max_length=20, choices=Status.choices, default=Status.PENDING)
    # Код, который покупатель называет курьеру или сотруднику ПВЗ при получении
    pickup_code = models.CharField('Код получения', max_length=6)
    storage_until = models.DateTimeField('Хранится в ПВЗ до', null=True, blank=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    delivered_at = models.DateTimeField('Получен', null=True, blank=True)

    class Meta:
        verbose_name = 'Доставка'
        verbose_name_plural = 'Доставки'
        ordering = ['-created_at']

    def __str__(self):
        return f'Доставка {self.seller_order}'

    def save(self, *args, **kwargs):
        if not self.pickup_code:
            self.pickup_code = f'{secrets.randbelow(10 ** 6):06d}'
        super().save(*args, **kwargs)

    @property
    def order(self):
        return self.seller_order.order

    @property
    def is_pickup(self):
        return self.order.delivery_type == Order.DeliveryType.PICKUP

    def _set_status(self, new_status, changed_by=None, comment='', extra_fields=()):
        if new_status not in self.TRANSITIONS[self.status]:
            raise DeliveryError(
                f'Нельзя перевести доставку из «{self.get_status_display()}» '
                f'в «{self.Status(new_status).label}»'
            )
        old_status = self.status
        self.status = new_status
        self.save(update_fields=['status', *extra_fields])
        DeliveryHistory.objects.create(delivery=self, old_status=old_status, new_status=new_status,
                                       changed_by=changed_by, comment=comment)

    @transaction.atomic
    def assign_courier(self, courier, changed_by=None):
        """Логист назначает (или меняет) курьера, пока посылка ещё на складе."""
        if courier.role != User.Role.COURIER:
            raise DeliveryError(f'{courier} — не курьер')
        self.courier = courier
        self._set_status(self.Status.ASSIGNED, changed_by, f'Курьер: {courier.full_name}', ['courier'])

    @transaction.atomic
    def pick_up(self, changed_by=None):
        """Курьер забрал посылку со склада → подзаказ «Передан в доставку»."""
        self._set_status(self.Status.IN_TRANSIT, changed_by)
        self.seller_order.change_status(SellerOrder.Status.SHIPPED, changed_by)

    @transaction.atomic
    def arrive_at_pickup_point(self, changed_by=None):
        """Посылка доставлена в ПВЗ — начинается срок хранения."""
        if not self.is_pickup:
            raise DeliveryError('Это курьерская доставка, а не доставка в пункт выдачи')
        self.storage_until = timezone.now() + timedelta(days=self.order.pickup_point.storage_days)
        self._set_status(self.Status.AT_PICKUP_POINT, changed_by,
                         f'Хранится до {self.storage_until:%d.%m.%Y}', ['storage_until'])

    @transaction.atomic
    def hand_over(self, code=None, changed_by=None):
        """Вручение покупателю (курьером или в ПВЗ). Код проверяется, если передан."""
        if self.is_pickup and self.status != self.Status.AT_PICKUP_POINT:
            raise DeliveryError('Посылка ещё не прибыла в пункт выдачи')
        if code is not None and code != self.pickup_code:
            raise DeliveryError('Неверный код получения')
        self.delivered_at = timezone.now()
        self._set_status(self.Status.DELIVERED, changed_by, extra_fields=['delivered_at'])
        self.seller_order.change_status(SellerOrder.Status.DELIVERED, changed_by)

    @transaction.atomic
    def return_to_warehouse(self, changed_by=None, comment=''):
        """Покупатель не получил посылку: товар на склад, деньги на баланс (через отмену подзаказа)."""
        comment = comment or ('Не забрали из пункта выдачи' if self.is_pickup else 'Не удалось вручить')
        self._set_status(self.Status.RETURNED, changed_by, comment)
        self.seller_order.change_status(SellerOrder.Status.CANCELLED, changed_by, comment)

    def cancel(self, changed_by=None, comment=''):
        """Вызывается при отмене подзаказа, пока посылка ещё на складе."""
        if self.status not in self.FINAL_STATUSES:
            self._set_status(self.Status.CANCELLED, changed_by, comment)

    @classmethod
    def return_expired(cls, changed_by=None):
        """Возвращает посылки, которые не забрали из ПВЗ до конца срока хранения."""
        expired = cls.objects.filter(status=cls.Status.AT_PICKUP_POINT, storage_until__lt=timezone.now())
        count = 0
        for delivery in expired:
            delivery.return_to_warehouse(changed_by, 'Истёк срок хранения в пункте выдачи')
            count += 1
        return count


class DeliveryHistory(models.Model):
    """История статусов доставки (требование ТЗ)."""

    delivery = models.ForeignKey(Delivery, verbose_name='Доставка', on_delete=models.CASCADE, related_name='history')
    old_status = models.CharField('Прежний статус', max_length=20, blank=True)
    new_status = models.CharField('Новый статус', max_length=20)
    changed_by = models.ForeignKey(User, verbose_name='Кто изменил', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    changed_at = models.DateTimeField('Когда', auto_now_add=True)
    comment = models.CharField('Комментарий', max_length=255, blank=True)

    class Meta:
        verbose_name = 'Изменение статуса доставки'
        verbose_name_plural = 'История доставки'
        ordering = ['changed_at']

    def __str__(self):
        return f'{self.delivery}: {self.old_status or "—"} → {self.new_status}'


def create_delivery(seller_order, changed_by=None):
    """Создаёт доставку для собранного подзаказа (вызывается из SellerOrder.change_status)."""
    delivery, created = Delivery.objects.get_or_create(seller_order=seller_order)
    if created:
        DeliveryHistory.objects.create(delivery=delivery, new_status=delivery.status,
                                       changed_by=changed_by, comment='Подзаказ собран')
    return delivery
