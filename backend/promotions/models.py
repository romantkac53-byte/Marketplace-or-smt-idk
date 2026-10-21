from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from catalog.models import Category, Product
from users.models import Seller

KOPECK = Decimal('0.01')


class Promotion(models.Model):
    """Акция: скидка на товары, категории или на всё (если ничего не выбрано)."""

    class DiscountType(models.TextChoices):
        PERCENT = 'percent', 'Процент'
        FIXED = 'fixed', 'Фиксированная сумма, ₽'

    name = models.CharField('Название', max_length=150)
    discount_type = models.CharField('Тип скидки', max_length=20, choices=DiscountType.choices)
    value = models.DecimalField('Размер скидки', max_digits=10, decimal_places=2,
                                validators=[MinValueValidator(Decimal('0.01'))])
    starts_at = models.DateTimeField('Начало')
    ends_at = models.DateTimeField('Окончание')
    is_active = models.BooleanField('Включена', default=True)
    # Пусто — акция всей площадки; задан — скидка только на товары этого продавца
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, null=True, blank=True,
                               related_name='promotions', verbose_name='Продавец')
    products = models.ManyToManyField(Product, blank=True, related_name='promotions', verbose_name='Товары')
    categories = models.ManyToManyField(Category, blank=True, related_name='promotions',
                                        verbose_name='Категории (вместе с подкатегориями)')
    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'Акция'
        verbose_name_plural = 'Акции'
        ordering = ['-starts_at']

    def __str__(self):
        sign = '%' if self.discount_type == self.DiscountType.PERCENT else ' ₽'
        # Decimal(str(...)) — value может быть int, пока объект не перечитан из базы;
        # format(..., 'f') — чтобы 30 не превратилось в «3E+1» после normalize()
        value = format(Decimal(str(self.value)).normalize(), 'f')
        return f'{self.name} (−{value}{sign})'

    def clean(self):
        errors = {}  # собираем все ошибки, чтобы форма показала их сразу, а не по одной
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors['ends_at'] = 'Окончание должно быть позже начала'
        if self.discount_type == self.DiscountType.PERCENT and self.value and self.value >= 100:
            errors['value'] = 'Скидка в процентах должна быть меньше 100'
        if errors:
            raise ValidationError(errors)

    @property
    def is_running(self):
        """Действует прямо сейчас."""
        now = timezone.now()
        return self.is_active and self.starts_at <= now < self.ends_at

    def applies_to(self, product):
        if self.seller_id and product.seller_id != self.seller_id:
            return False
        product_ids = {p.pk for p in self.products.all()}
        category_ids = {c.pk for c in self.categories.all()}
        if not product_ids and not category_ids:
            return True  # ничего не выбрано — на все товары
        if product.pk in product_ids:
            return True
        # Акция на «Лекарства» действует и на «Спреи»
        return any(c.pk in category_ids for c in product.category.get_ancestors(include_self=True))

    def discount_for(self, price):
        """Размер скидки в рублях для цены price (не больше самой цены)."""
        if self.discount_type == self.DiscountType.PERCENT:
            discount = (price * self.value / 100).quantize(KOPECK, rounding=ROUND_HALF_UP)
        else:
            discount = self.value
        return min(discount, price)


class PriceCalculator:
    """Загружает действующие акции один раз и считает цены для многих товаров.
    Нужен для списков: иначе каждый товар делал бы свой запрос к акциям."""

    def __init__(self):
        now = timezone.now()
        self.promotions = list(
            Promotion.objects.filter(is_active=True, starts_at__lte=now, ends_at__gt=now)
            .prefetch_related('products', 'categories')
        )

    def best(self, product):
        """Самая выгодная для покупателя действующая акция: (акция, скидка ₽) или (None, 0)."""
        best, best_discount = None, Decimal('0')
        for promo in self.promotions:
            if promo.applies_to(product):
                discount = promo.discount_for(product.price)
                if discount > best_discount:
                    best, best_discount = promo, discount
        return best, best_discount


def best_promotion(product):
    """Лучшая акция для одного товара."""
    return PriceCalculator().best(product)
