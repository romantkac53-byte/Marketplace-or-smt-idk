from decimal import ROUND_HALF_UP, Decimal

from django.core.validators import MinValueValidator
from django.db import models, transaction

from catalog.models import Product
from marketplace.errors import DomainError
from promotions.models import best_promotion
from users.models import Customer, Seller, User
from warehouse.models import StockError, StockMovement, move_stock


def label(text):
    """Подпись колонки в админке для вычисляемых свойств (иначе будет английское имя)."""
    def decorator(func):
        func.short_description = text
        return func
    return decorator


class OrderError(DomainError):
    """Ошибка бизнес-логики заказа: недопустимый переход статуса, нет товара и т.п."""


class Order(models.Model):
    """Заказ покупателя целиком. Оплачивается одним платежом, делится на подзаказы продавцов."""

    class Status(models.TextChoices):
        NEW = 'new', 'Ожидает оплаты'
        PAID = 'paid', 'Оплачен'
        COMPLETED = 'completed', 'Выполнен'
        CANCELLED = 'cancelled', 'Отменён'

    class DeliveryType(models.TextChoices):
        COURIER = 'courier', 'Курьером на адрес'
        PICKUP = 'pickup', 'В пункт выдачи'

    # Customer 1 — 0..* Order. PROTECT: покупателя с заказами удалить нельзя, история важнее
    customer = models.ForeignKey(Customer, verbose_name='Покупатель', on_delete=models.PROTECT, related_name='orders')
    status = models.CharField('Статус', max_length=20, choices=Status.choices, default=Status.NEW)
    delivery_type = models.CharField('Способ получения', max_length=20,
                                     choices=DeliveryType.choices, default=DeliveryType.COURIER)
    # Строкой 'delivery.PickupPoint', а не импортом: delivery сам импортирует orders
    pickup_point = models.ForeignKey('delivery.PickupPoint', on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='orders', verbose_name='Пункт выдачи')
    # Для ПВЗ сюда копируется адрес пункта — чтобы в заказе всегда был понятный адрес
    delivery_address = models.CharField('Адрес доставки', max_length=255)
    created_at = models.DateTimeField('Дата', auto_now_add=True)  # date с диаграммы

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ №{self.pk}'

    @property
    def items(self):
        """Все позиции заказа через подзаказы (Order ◆— OrderItem с диаграммы)."""
        return OrderItem.objects.filter(seller_order__order=self)

    @property
    @label('Сумма заказа')
    def total_amount(self):
        return sum((so.subtotal for so in self.seller_orders.all()), Decimal('0'))

    def _set_status(self, new_status, changed_by=None, comment=''):
        old_status = self.status
        self.status = new_status
        self.save(update_fields=['status'])
        StatusHistory.objects.create(
            order=self, old_status=old_status, new_status=new_status,
            changed_by=changed_by, comment=comment,
        )

    def get_payment(self):
        return getattr(self, 'payment', None)  # у заказа может не быть платежа — вернётся None

    def pay(self, changed_by=None):
        """Оплата заказа с баланса покупателя."""
        payment = self.get_payment()
        if payment is None:
            raise OrderError('У заказа нет платежа')
        try:
            payment.process(changed_by)
        finally:
            self.refresh_from_db(fields=['status'])  # статус поменялся через объект платежа, а не через self

    @transaction.atomic
    def confirm(self, changed_by=None):
        """confirm() с диаграммы: заказ оплачен — подзаказы уходят продавцам в работу.
        Вызывается только из оплаты (Payment.process())."""
        if self.status != self.Status.NEW:
            raise OrderError(f'Подтвердить можно только заказ в статусе «{self.Status.NEW.label}»')
        self._set_status(self.Status.PAID, changed_by, 'Заказ оплачен')

    @transaction.atomic
    def cancel(self, changed_by=None, comment=''):
        """cancel() с диаграммы: отмена всего заказа, пока ни один подзаказ не передан в доставку."""
        if self.status in (self.Status.COMPLETED, self.Status.CANCELLED):
            raise OrderError('Заказ уже завершён или отменён')
        active = self.seller_orders.exclude(status=SellerOrder.Status.CANCELLED)
        if active.filter(status__in=SellerOrder.SHIPPED_STATUSES).exists():
            raise OrderError('Часть заказа уже передана в доставку — отменить весь заказ нельзя')
        for so in active:
            so.cancel(changed_by, comment or 'Отмена всего заказа', sync_order=False)
        self._set_status(self.Status.CANCELLED, changed_by, comment)
        self._cancel_unpaid_payment()

    def _cancel_unpaid_payment(self):
        payment = self.get_payment()
        if payment is not None:
            payment.refresh_from_db()  # платёж мог измениться при отмене подзаказов
            payment.cancel()  # для оплаченного ничего не делает: деньги уже вернулись через подзаказы

    def sync_status(self, changed_by=None):
        """Статус заказа следует за подзаказами: все доставлены → выполнен, все отменены → отменён."""
        if self.status in (self.Status.COMPLETED, self.Status.CANCELLED):
            return
        statuses = set(self.seller_orders.values_list('status', flat=True))
        if statuses == {SellerOrder.Status.CANCELLED}:
            self._set_status(self.Status.CANCELLED, changed_by, 'Все подзаказы отменены')
            self._cancel_unpaid_payment()
        elif statuses and statuses <= {SellerOrder.Status.DELIVERED, SellerOrder.Status.CANCELLED}:
            self._set_status(self.Status.COMPLETED, changed_by, 'Все подзаказы доставлены или отменены')


class SellerOrder(models.Model):
    """Подзаказ: часть заказа покупателя, которую выполняет один продавец."""

    class Status(models.TextChoices):
        NEW = 'new', 'Новый'
        CONFIRMED = 'confirmed', 'Подтверждён продавцом'
        ASSEMBLING = 'assembling', 'Собирается на складе'
        READY = 'ready', 'Собран, ждёт курьера'
        SHIPPED = 'shipped', 'Передан в доставку'
        DELIVERED = 'delivered', 'Доставлен'
        CANCELLED = 'cancelled', 'Отменён'

    # Разрешённые переходы: из какого статуса — в какие
    TRANSITIONS = {
        Status.NEW: [Status.CONFIRMED, Status.CANCELLED],
        Status.CONFIRMED: [Status.ASSEMBLING, Status.CANCELLED],
        Status.ASSEMBLING: [Status.READY, Status.CANCELLED],
        Status.READY: [Status.SHIPPED, Status.CANCELLED],
        Status.SHIPPED: [Status.DELIVERED, Status.CANCELLED],  # отмена в пути — если посылку не получили
        Status.DELIVERED: [],
        Status.CANCELLED: [],
    }
    SHIPPED_STATUSES = [Status.SHIPPED, Status.DELIVERED]

    order = models.ForeignKey(Order, verbose_name='Заказ', on_delete=models.CASCADE, related_name='seller_orders')
    # PROTECT: продавца с заказами удалить нельзя (вместо удаления — статус blocked)
    seller = models.ForeignKey(Seller, verbose_name='Продавец', on_delete=models.PROTECT, related_name='orders')
    status = models.CharField('Статус', max_length=20, choices=Status.choices, default=Status.NEW)
    updated_at = models.DateTimeField('Изменён', auto_now=True)

    class Meta:
        verbose_name = 'Подзаказ продавца'
        verbose_name_plural = 'Подзаказы продавцов'
        ordering = ['-order__created_at']
        constraints = [
            models.UniqueConstraint(fields=['order', 'seller'], name='one_suborder_per_seller'),
        ]

    def __str__(self):
        return f'{self.order} / {self.seller}'

    @property
    @label('Сумма')
    def subtotal(self):
        return sum((item.calculate_subtotal() for item in self.items.all()), Decimal('0'))

    @property
    @label('Комиссия площадки')
    def commission(self):
        """Комиссия площадки с подзаказа, ₽."""
        return sum((item.commission for item in self.items.all()), Decimal('0'))

    @property
    @label('Продавцу')
    def seller_payout(self):
        """Сколько получает продавец: сумма подзаказа минус комиссия."""
        return self.subtotal - self.commission

    @transaction.atomic
    def change_status(self, new_status, changed_by=None, comment='', sync_order=True):
        if new_status not in self.TRANSITIONS[self.status]:
            raise OrderError(
                f'Нельзя перевести подзаказ из «{self.get_status_display()}» '
                f'в «{self.Status(new_status).label}»'
            )
        # Продавец берёт подзаказ в работу только после оплаты всего заказа
        if self.status == self.Status.NEW and new_status != self.Status.CANCELLED:
            # Статус берём из базы: объект заказа в памяти мог устареть
            if Order.objects.values_list('status', flat=True).get(pk=self.order_id) != Order.Status.PAID:
                raise OrderError('Заказ ещё не оплачен')

        old_status = self.status
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])
        StatusHistory.objects.create(
            order=self.order, seller_order=self, old_status=old_status,
            new_status=new_status, changed_by=changed_by, comment=comment,
        )
        from delivery.models import Delivery, create_delivery  # импорт внутри: delivery импортирует orders

        if new_status == self.Status.READY:
            create_delivery(self, changed_by)  # склад собрал — посылка ждёт курьера
        if new_status == self.Status.SHIPPED:
            self._move_items(StockMovement.Type.SHIPMENT, changed_by)  # товар физически покинул склад
        if new_status == self.Status.CANCELLED:
            delivery = Delivery.objects.filter(seller_order=self).first()
            if delivery is not None:
                delivery.cancel(changed_by, comment)  # если доставка уже завершена — ничего не делает
            # До отгрузки товар лежит на складе — просто снимаем резерв; после — он вернулся обратно
            stock_type = StockMovement.Type.RETURN if old_status == self.Status.SHIPPED else StockMovement.Type.RELEASE
            self._move_items(stock_type, changed_by)
            payment = self.order.get_payment()
            if payment is not None:
                # Оплачено — сумма подзаказа возвращается на баланс; не оплачено — уменьшается сумма к оплате
                payment.on_suborder_cancelled(self.subtotal, changed_by, f'Отмена: {self}')
        if sync_order:
            self.order.sync_status(changed_by)

    def confirm(self, changed_by=None):
        self.change_status(self.Status.CONFIRMED, changed_by)

    def cancel(self, changed_by=None, comment='', sync_order=True):
        self.change_status(self.Status.CANCELLED, changed_by, comment, sync_order)

    def _move_items(self, stock_type, changed_by=None):
        for item in self.items.select_related('product'):
            move_stock(item.product, stock_type, item.quantity, seller_order=self,
                       created_by=changed_by, comment=str(self))


class OrderItem(models.Model):
    seller_order = models.ForeignKey(SellerOrder, verbose_name='Подзаказ', on_delete=models.CASCADE, related_name='items')
    # OrderItem 0..* — 1 Product. PROTECT: товар из заказов удалить нельзя (можно снять с продажи)
    product = models.ForeignKey(Product, verbose_name='Товар', on_delete=models.PROTECT, related_name='order_items')
    # Всё ниже копируется в момент покупки и больше не меняется
    product_name = models.CharField('Название товара', max_length=200)
    # price — сколько заплатил покупатель за штуку (со скидкой); original_price — цена в каталоге без скидки
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    original_price = models.DecimalField('Цена без скидки', max_digits=10, decimal_places=2,
                                         validators=[MinValueValidator(0)])
    promotion = models.ForeignKey('promotions.Promotion', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='order_items', verbose_name='Акция')
    commission_percent = models.DecimalField('Комиссия, %', max_digits=5, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField('Количество', validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        return f'{self.product_name} × {self.quantity}'

    @label('Сумма')
    def calculate_subtotal(self):
        """calculateSubtotal() с диаграммы."""
        return self.price * self.quantity

    @property
    @label('Скидка')
    def discount(self):
        """Скидка на всю позицию, ₽."""
        return (self.original_price - self.price) * self.quantity

    @property
    @label('Комиссия площадки')
    def commission(self):
        """Комиссия площадки с позиции, ₽ (от цены, которую заплатил покупатель)."""
        return (self.calculate_subtotal() * self.commission_percent / 100).quantize(Decimal('0.01'), ROUND_HALF_UP)

    @property
    @label('Продавцу')
    def seller_payout(self):
        """Сколько получает продавец за позицию."""
        return self.calculate_subtotal() - self.commission


class StatusHistory(models.Model):
    """История статусов (требование ТЗ). seller_order пустой — изменился статус всего заказа."""

    order = models.ForeignKey(Order, verbose_name='Заказ', on_delete=models.CASCADE, related_name='history')
    seller_order = models.ForeignKey(
        SellerOrder, verbose_name='Подзаказ', on_delete=models.CASCADE, null=True, blank=True, related_name='history',
    )
    old_status = models.CharField('Прежний статус', max_length=20, blank=True)
    new_status = models.CharField('Новый статус', max_length=20)
    changed_by = models.ForeignKey(User, verbose_name='Кто изменил', on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField('Когда', auto_now_add=True)
    comment = models.CharField('Комментарий', max_length=255, blank=True)

    class Meta:
        verbose_name = 'Изменение статуса'
        verbose_name_plural = 'История статусов'
        ordering = ['changed_at']

    def __str__(self):
        target = self.seller_order or self.order
        return f'{target}: {self.old_status or "—"} → {self.new_status}'


@transaction.atomic
def place_order(customer, delivery_address='', pickup_point=None):
    """Оформление заказа из корзины: проверка и резерв товара, разбиение по продавцам, очистка корзины.
    pickup_point передан — доставка в ПВЗ, иначе курьером на адрес."""
    cart = getattr(customer, 'cart', None)
    if cart is None or not cart.items.exists():
        raise OrderError('Корзина пуста')

    if pickup_point is not None:
        if not pickup_point.is_active:
            raise OrderError(f'Пункт выдачи «{pickup_point.name}» сейчас не работает')
        delivery_type, address = Order.DeliveryType.PICKUP, pickup_point.address
    else:
        delivery_type, address = Order.DeliveryType.COURIER, delivery_address or customer.address
        if not address:
            raise OrderError('Не указан адрес доставки')

    order = Order.objects.create(customer=customer, delivery_type=delivery_type,
                                 pickup_point=pickup_point, delivery_address=address)
    StatusHistory.objects.create(order=order, new_status=order.status,
                                 changed_by=customer.user, comment='Заказ оформлен')

    for seller, cart_items in cart.items_by_seller().items():
        if not seller.is_active:
            raise OrderError(f'Продавец «{seller}» сейчас не принимает заказы')
        seller_order = SellerOrder.objects.create(order=order, seller=seller)
        StatusHistory.objects.create(order=order, seller_order=seller_order,
                                     new_status=seller_order.status, changed_by=customer.user)
        for cart_item in cart_items:
            product = cart_item.product
            if not product.is_active:
                raise OrderError(f'Товар «{product.name}» снят с продажи')
            try:
                # Резерв: товар остаётся на складе, но купить его уже нельзя
                move_stock(product, StockMovement.Type.RESERVE, cart_item.quantity,
                           seller_order=seller_order, created_by=customer.user, comment=f'Оформление {order}')
            except StockError as e:
                raise OrderError(str(e)) from e  # нехватка — откатывается весь заказ
            # Цена со скидкой по лучшей акции и процент комиссии фиксируются на момент покупки
            promotion, discount = best_promotion(product)
            OrderItem.objects.create(
                seller_order=seller_order, product=product, product_name=product.name,
                original_price=product.price, price=product.price - discount, promotion=promotion,
                commission_percent=product.category.get_commission_percent(),
                quantity=cart_item.quantity,
            )

    cart.items.all().delete()

    from payments.models import Payment  # импорт внутри: payments сам импортирует orders
    Payment.objects.create(order=order, amount=order.total_amount)
    return order
