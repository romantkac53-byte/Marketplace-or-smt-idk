from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from orders.models import Order, OrderError
from users.models import Customer, User


class PaymentError(OrderError):
    """Ошибка оплаты: не хватает денег, заказ уже оплачен и т.п."""


class BalanceTransaction(models.Model):
    """Журнал движения денег на балансе покупателя. Записи не меняются и не удаляются."""

    class Type(models.TextChoices):
        TOPUP = 'topup', 'Пополнение'
        PAYMENT = 'payment', 'Оплата заказа'
        REFUND = 'refund', 'Возврат'

    customer = models.ForeignKey(Customer, verbose_name='Покупатель', on_delete=models.PROTECT, related_name='balance_transactions')
    type = models.CharField('Тип', max_length=20, choices=Type.choices)
    # Со знаком: пополнение и возврат > 0, оплата < 0
    amount = models.DecimalField('Сумма', max_digits=12, decimal_places=2)
    balance_after = models.DecimalField('Баланс после', max_digits=12, decimal_places=2)
    order = models.ForeignKey(Order, verbose_name='Заказ', on_delete=models.PROTECT, null=True, blank=True,
                              related_name='balance_transactions')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name='Кто провёл')
    comment = models.CharField('Комментарий', max_length=255, blank=True)
    created_at = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Операция по балансу'
        verbose_name_plural = 'Операции по балансу'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_type_display()} {self.amount:+} ₽ — {self.customer}'


@transaction.atomic
def change_balance(customer, amount, type, order=None, created_by=None, comment=''):
    """Единственное место, где меняется баланс: изменение + запись в журнал в одной транзакции."""
    amount = Decimal(str(amount))
    # Блокируем строку покупателя: два одновременных списания не уведут баланс в минус
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    new_balance = customer.balance + amount
    if new_balance < 0:
        raise PaymentError(f'Недостаточно средств: на балансе {customer.balance} ₽, нужно {-amount} ₽')
    customer.balance = new_balance
    customer.save(update_fields=['balance'])
    return BalanceTransaction.objects.create(
        customer=customer, type=type, amount=amount, balance_after=new_balance,
        order=order, created_by=created_by, comment=comment,
    )


def top_up(customer, amount, created_by=None, comment=''):
    """Пополнение баланса (из админки)."""
    if Decimal(str(amount)) <= 0:
        raise PaymentError('Сумма пополнения должна быть больше нуля')
    return change_balance(customer, amount, BalanceTransaction.Type.TOPUP,
                          created_by=created_by, comment=comment)


class Payment(models.Model):
    """Оплата заказа (Order 1 — 1 Payment). Имитация: деньги списываются с внутреннего баланса."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает оплаты'
        PAID = 'paid', 'Оплачен'
        FAILED = 'failed', 'Ошибка оплаты'
        PARTIALLY_REFUNDED = 'partially_refunded', 'Частично возвращён'
        REFUNDED = 'refunded', 'Возвращён'
        CANCELLED = 'cancelled', 'Отменён'

    order = models.OneToOneField(Order, verbose_name='Заказ', on_delete=models.PROTECT, related_name='payment')
    amount = models.DecimalField('Сумма', max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    refunded_amount = models.DecimalField('Возвращено', max_digits=12, decimal_places=2, default=0)
    status = models.CharField('Статус', max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.CharField('Причина ошибки', max_length=255, blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    paid_at = models.DateTimeField('Оплачен', null=True, blank=True)

    class Meta:
        verbose_name = 'Платёж'
        verbose_name_plural = 'Платежи'
        ordering = ['-created_at']

    def __str__(self):
        return f'Платёж по {self.order}'

    @property
    def is_paid(self):
        return self.status in (self.Status.PAID, self.Status.PARTIALLY_REFUNDED)

    def _lock(self):
        """Перечитывает платёж из базы и блокирует строку до конца транзакции.
        Объект в памяти мог устареть (например, после отката неудачной операции) —
        считать деньги по нему нельзя."""
        self.refresh_from_db(from_queryset=Payment.objects.select_for_update())

    def process(self, changed_by=None):
        """process() с диаграммы: списывает сумму с баланса и подтверждает заказ."""
        error = None
        with transaction.atomic():
            self._lock()
            if self.status not in (self.Status.PENDING, self.Status.FAILED):
                raise PaymentError(f'Оплатить нельзя: платёж в статусе «{self.get_status_display()}»')
            try:
                with transaction.atomic():
                    change_balance(self.order.customer, -self.amount, BalanceTransaction.Type.PAYMENT,
                                   order=self.order, created_by=changed_by, comment=f'Оплата {self.order}')
                    self.status = self.Status.PAID
                    self.paid_at = timezone.now()
                    self.error_message = ''
                    self.save(update_fields=['status', 'paid_at', 'error_message'])
                    self.order.confirm(changed_by)
            except PaymentError as e:
                # Неудачная попытка сохраняется, чтобы её было видно; повторить можно после пополнения
                error = e
                self.status = self.Status.FAILED
                self.error_message = str(e)
                self.save(update_fields=['status', 'error_message'])
        if error is not None:
            raise error  # снаружи транзакции — чтобы сохранённый статус «Ошибка оплаты» не откатился

    @transaction.atomic
    def on_suborder_cancelled(self, amount, changed_by=None, comment=''):
        """Вызывается при отмене подзаказа."""
        self._lock()
        if self.is_paid:
            self.refund(amount, changed_by, comment)
        elif self.status in (self.Status.PENDING, self.Status.FAILED):
            # Ещё не оплачено — просто не берём деньги за отменённую часть
            self.amount = max(self.amount - Decimal(str(amount)), Decimal('0'))
            self.save(update_fields=['amount'])

    @transaction.atomic
    def refund(self, amount, changed_by=None, comment=''):
        """Возврат части или всей суммы на баланс. Возвращает сумму, которую реально вернули."""
        self._lock()
        amount = min(Decimal(str(amount)), self.amount - self.refunded_amount)  # больше оплаченного не вернём
        if not self.is_paid or amount <= 0:
            return Decimal('0')
        change_balance(self.order.customer, amount, BalanceTransaction.Type.REFUND,
                       order=self.order, created_by=changed_by, comment=comment)
        self.refunded_amount += amount
        self.status = (self.Status.REFUNDED if self.refunded_amount >= self.amount
                       else self.Status.PARTIALLY_REFUNDED)
        self.save(update_fields=['refunded_amount', 'status'])
        return amount

    @transaction.atomic
    def cancel(self):
        """Отмена неоплаченного платежа вместе с заказом."""
        self._lock()
        if self.status in (self.Status.PENDING, self.Status.FAILED):
            self.status = self.Status.CANCELLED
            self.save(update_fields=['status'])
