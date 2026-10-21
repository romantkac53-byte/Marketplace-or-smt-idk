from django.db import models, transaction

from catalog.models import Product
from marketplace.errors import DomainError
from users.models import User


class StockError(DomainError, ValueError):
    """Ошибка склада: не хватает товара, нельзя списать зарезервированное и т.п."""


class StockMovement(models.Model):
    """Журнал движения товара. Записи не меняются и не удаляются."""

    class Type(models.TextChoices):
        RECEIPT = 'receipt', 'Приход (поставка)'
        RESERVE = 'reserve', 'Резерв под заказ'
        RELEASE = 'release', 'Снятие резерва (отмена)'
        SHIPMENT = 'shipment', 'Отгрузка курьеру'
        RETURN = 'return', 'Возврат на склад'
        WRITE_OFF = 'write_off', 'Списание'
        INVENTORY = 'inventory', 'Инвентаризация'

    # Ручные операции склада (доступны в админке); остальные делает система по заказам
    MANUAL_TYPES = [Type.RECEIPT, Type.WRITE_OFF, Type.INVENTORY]

    product = models.ForeignKey(Product, verbose_name='Товар', on_delete=models.PROTECT, related_name='stock_movements')
    type = models.CharField('Операция', max_length=20, choices=Type.choices)
    quantity = models.PositiveIntegerField('Количество')  # для инвентаризации — фактический остаток
    stock_delta = models.IntegerField('Изм. остатка')
    reserved_delta = models.IntegerField('Изм. резерва')
    stock_after = models.PositiveIntegerField('Остаток после')
    reserved_after = models.PositiveIntegerField('Резерв после')
    # Строкой, а не импортом: orders сам импортирует warehouse
    seller_order = models.ForeignKey('orders.SellerOrder', on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='stock_movements', verbose_name='Подзаказ')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name='Кто провёл')
    comment = models.CharField('Комментарий', max_length=255, blank=True)
    created_at = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Движение товара'
        verbose_name_plural = 'Движение товаров'
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return f'{self.get_type_display()}: {self.product} ({self.stock_delta:+}/{self.reserved_delta:+})'


# Как каждая операция меняет (физический остаток, резерв) при количестве q
_DELTAS = {
    StockMovement.Type.RECEIPT: lambda q: (q, 0),
    StockMovement.Type.RESERVE: lambda q: (0, q),
    StockMovement.Type.RELEASE: lambda q: (0, -q),
    StockMovement.Type.SHIPMENT: lambda q: (-q, -q),
    StockMovement.Type.RETURN: lambda q: (q, 0),
    StockMovement.Type.WRITE_OFF: lambda q: (-q, 0),
}


@transaction.atomic
def move_stock(product, type, quantity, seller_order=None, created_by=None, comment=''):
    """Единственное место, где меняются остаток и резерв: изменение + запись в журнал."""
    if quantity < 0 or (quantity == 0 and type != StockMovement.Type.INVENTORY):
        raise StockError('Количество должно быть больше нуля')

    # Блокируем строку товара: два заказа не зарезервируют одну последнюю единицу
    locked = Product.objects.select_for_update().get(pk=product.pk)

    if type == StockMovement.Type.INVENTORY:
        stock_delta, reserved_delta = quantity - locked.stock, 0  # quantity — сколько насчитали
    else:
        stock_delta, reserved_delta = _DELTAS[type](quantity)

    new_stock = locked.stock + stock_delta
    new_reserved = locked.reserved + reserved_delta
    if type == StockMovement.Type.RESERVE and quantity > locked.available:
        raise StockError(f'Недостаточно товара «{locked.name}»: доступно {locked.available}, нужно {quantity}')
    if new_stock < 0 or new_reserved < 0:
        raise StockError(f'Недостаточно товара «{locked.name}» на складе: есть {locked.stock}')
    if new_stock < new_reserved:
        raise StockError(
            f'Нельзя: на складе останется {new_stock} шт. «{locked.name}», '
            f'а под заказы зарезервировано {new_reserved}'
        )

    locked.stock, locked.reserved = new_stock, new_reserved
    locked.save(update_fields=['stock', 'reserved', 'updated_at'])
    # Обновляем и объект, который передали, чтобы у вызывающего кода были свежие цифры
    product.stock, product.reserved = new_stock, new_reserved

    return StockMovement.objects.create(
        product=locked, type=type, quantity=quantity,
        stock_delta=stock_delta, reserved_delta=reserved_delta,
        stock_after=new_stock, reserved_after=new_reserved,
        seller_order=seller_order, created_by=created_by, comment=comment,
    )
