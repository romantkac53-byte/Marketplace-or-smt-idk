from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import Product
from marketplace.errors import DomainError
from users.models import Customer


class CartError(DomainError, ValueError):
    """Ошибка корзины: товар недоступен, не хватает на складе."""


class Cart(models.Model):
    # У каждого покупателя ровно одна корзина
    customer = models.OneToOneField(Customer, verbose_name='Покупатель', on_delete=models.CASCADE, related_name='cart')
    updated_at = models.DateTimeField('Изменена', auto_now=True)

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

    def __str__(self):
        return f'Корзина {self.customer}'

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.select_related('product'))

    def add_product(self, product, quantity=1):
        """Добавляет товар; если он уже в корзине — увеличивает количество."""
        item = self.items.filter(product=product).first()
        new_quantity = (item.quantity if item else 0) + quantity
        self._check(product, quantity, new_quantity)
        if item:
            item.quantity = new_quantity
            item.save(update_fields=['quantity'])
        else:
            item = self.items.create(product=product, quantity=new_quantity)
        self.save(update_fields=['updated_at'])
        return item

    def set_quantity(self, item, quantity):
        """Устанавливает количество позиции (кнопки «+» и «−» в корзине)."""
        self._check(item.product, quantity, quantity)
        item.quantity = quantity
        item.save(update_fields=['quantity'])
        self.save(update_fields=['updated_at'])
        return item

    @staticmethod
    def _check(product, quantity, new_quantity):
        if quantity < 1:
            raise CartError('Количество должно быть не меньше 1')
        # Остаток мог измениться, пока объект товара лежал в памяти (кто-то оформил заказ)
        product.refresh_from_db(fields=['stock', 'reserved', 'is_active'])
        if not product.is_active or not product.seller.is_active:
            raise CartError(f'Товар «{product.name}» сейчас недоступен для покупки')
        if new_quantity > product.available:
            raise CartError(f'Доступно только {product.available} шт. товара «{product.name}»')

    def items_by_seller(self):
        """Группировка позиций по продавцам — основа для разбиения заказа на подзаказы."""
        groups = {}
        for item in self.items.select_related('product__seller'):
            groups.setdefault(item.product.seller, []).append(item)
        return groups


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, verbose_name='Корзина', on_delete=models.CASCADE, related_name='items')
    # Если товар удалён из каталога, он просто исчезает из корзин
    product = models.ForeignKey(Product, verbose_name='Товар', on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField('Количество', default=1, validators=[MinValueValidator(1)])
    added_at = models.DateTimeField('Добавлен', auto_now_add=True)

    class Meta:
        verbose_name = 'Позиция корзины'
        verbose_name_plural = 'Позиции корзины'
        # Один товар — одна строка в корзине; повторное добавление увеличивает quantity/количество
        constraints = [
            models.UniqueConstraint(fields=['cart', 'product'], name='unique_product_in_cart'),
        ]

    def __str__(self):
        return f'{self.product} × {self.quantity}'

    @property
    def total_price(self):
        # Цена берётся текущая из каталога с учётом акций: в корзине она не фиксируется
        return self.product.current_price * self.quantity
