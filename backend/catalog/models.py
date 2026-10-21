import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from marketplace.errors import DomainError
from users.models import Seller


class CatalogError(DomainError, ValueError):
    """Ошибка каталога: например, отрицательная цена."""


class Category(models.Model):
    """Дерево категорий: Лекарства → Спреи. Товары лежат только в конечных категориях."""

    name = models.CharField('Название', max_length=100)
    slug = models.SlugField('Код для адреса (slug)', max_length=120, unique=True)
    parent = models.ForeignKey(
        'self', verbose_name='Родительская категория',
        on_delete=models.PROTECT,  # нельзя удалить категорию, пока у неё есть подкатегории
        null=True,
        blank=True,
        related_name='children',
    )
    # Пусто — берётся у родительской категории, а у корневой — общий процент из настроек
    commission_percent = models.DecimalField(
        'Комиссия площадки, %', max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Пусто — как у родительской категории (или общий процент площадки)',
    )

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self): 
        return ' → '.join(c.name for c in self.get_ancestors(include_self=True))

    def clean(self):
        # Защита от цикла: категория не может быть вложена сама в себя или в своего потомка
        if self.pk and self.parent_id:
            if self.parent_id == self.pk or self.parent in self.get_descendants():
                raise ValidationError({'parent': 'Категория не может быть вложена сама в себя.'})
        # В категорию с товарами нельзя добавить подкатегорию: товары окажутся «посередине» дерева
        if self.parent_id and self.parent.products.exists():
            raise ValidationError({'parent': 'В этой категории уже есть товары — подкатегорию в неё добавить нельзя.'})

    def get_commission_percent(self):
        """Процент комиссии: свой → у ближайшего родителя → общий из настроек."""
        for category in reversed(self.get_ancestors(include_self=True)):
            if category.commission_percent is not None:
                return category.commission_percent
        return Decimal(str(settings.MARKETPLACE_COMMISSION_PERCENT))

    def add_subcategory(self, name, slug):
        """addSubcategory() с диаграммы."""
        sub = Category(name=name, slug=slug, parent=self)
        sub.full_clean()
        sub.save()
        return sub

    def get_ancestors(self, include_self=False):
        """Цепочка от корня до категории: [Лекарства, Спреи]."""
        chain = [self] if include_self else []
        node = self.parent
        while node is not None:
            chain.append(node)
            node = node.parent
        return list(reversed(chain))

    def get_descendants(self):
        """Все подкатегории на любой глубине — для поиска товаров по родительской категории."""
        result = []
        level = list(self.children.all())
        while level:
            result.extend(level)
            level = list(Category.objects.filter(parent__in=level))
        return result

    @property
    def is_leaf(self):
        return not self.children.exists()


ARTICLE_MIN, ARTICLE_MAX = 100_000_000, 999_999_999  # артикул — 9 цифр, как на маркетплейсах


def generate_article():
    """Случайный незанятый артикул. Случайный, а не по порядку — чтобы по номеру
    нельзя было вычислить, сколько товаров на площадке."""
    while True:
        article = ARTICLE_MIN + secrets.randbelow(ARTICLE_MAX - ARTICLE_MIN + 1)
        if not Product.objects.filter(article=article).exists():
            return article


class Product(models.Model):
    # Артикул — уникальный номер товара для поиска (ID123456789) и копирования. Не меняется.
    article = models.PositiveBigIntegerField('Артикул', unique=True, editable=False)
    category = models.ForeignKey(Category, verbose_name='Категория', on_delete=models.PROTECT, related_name='products')
    seller = models.ForeignKey(Seller, verbose_name='Продавец', on_delete=models.CASCADE, related_name='products')
    name = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True)
    image = models.ImageField('Главное фото', upload_to='products/', blank=True)
    price = models.DecimalField('Цена', 
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    # Меняются только через warehouse.models.move_stock — каждое изменение попадает в журнал склада
    stock = models.PositiveIntegerField('Остаток на складе', default=0, editable=False)
    reserved = models.PositiveIntegerField('В резерве', default=0, editable=False)
    is_active = models.BooleanField('В продаже', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Изменён', auto_now=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.article:
            self.article = generate_article()
        super().save(*args, **kwargs)

    def clean(self):
        if self.category_id and not self.category.is_leaf:
            raise ValidationError({'category': 'Выберите конечную категорию (без подкатегорий), например «Спреи», а не «Лекарства».'})

    @property
    def available(self):
        """Сколько можно купить: физический остаток минус обещанное в заказах."""
        return self.stock - self.reserved

    @property
    def in_stock(self):
        return self.available > 0

    @property
    def active_promotion(self):
        """Самая выгодная действующая акция на товар (или None)."""
        from promotions.models import best_promotion  # импорт внутри: promotions импортирует catalog

        return best_promotion(self)[0]

    @property
    def current_price(self):
        """Цена для покупателя с учётом лучшей действующей акции."""
        from promotions.models import best_promotion

        return self.price - best_promotion(self)[1]

    @property
    def rating(self):
        """Средний рейтинг по опубликованным отзывам: {'avg': 4.5, 'count': 12}."""
        from reviews.models import product_rating  # импорт внутри: reviews импортирует catalog

        return product_rating(self)

    def update_price(self, new_price):
        """updatePrice() с диаграммы."""
        new_price = Decimal(str(new_price))
        if new_price < 0:
            raise CatalogError('Цена не может быть отрицательной')
        self.price = new_price
        self.save(update_fields=['price', 'updated_at'])

    def update_stock(self, delta, created_by=None, comment=''):
        """updateStock() с диаграммы: delta > 0 — приход на склад, delta < 0 — списание."""
        from warehouse.models import StockMovement, move_stock  # импорт внутри: warehouse импортирует catalog

        type = StockMovement.Type.RECEIPT if delta > 0 else StockMovement.Type.WRITE_OFF
        return move_stock(self, type, abs(delta), created_by=created_by, comment=comment)


class Characteristic(models.Model):
    """Название характеристики из ТЗ: «Объём», «Цвет», «Страна производства»…"""

    name = models.CharField('Название', max_length=100, unique=True)
    unit = models.CharField('Единица измерения', max_length=20, blank=True)

    class Meta:
        verbose_name = 'Характеристика'
        verbose_name_plural = 'Характеристики'
        ordering = ['name']

    def __str__(self):
        return f'{self.name}, {self.unit}' if self.unit else self.name


class ProductCharacteristic(models.Model):
    """Значение характеристики у конкретного товара: Объём = 20 мл."""

    product = models.ForeignKey(Product, verbose_name='Товар', on_delete=models.CASCADE, related_name='characteristics')
    characteristic = models.ForeignKey(Characteristic, verbose_name='Характеристика', on_delete=models.PROTECT, related_name='values')
    value = models.CharField('Значение', max_length=200)

    class Meta:
        verbose_name = 'Характеристика товара'
        verbose_name_plural = 'Характеристики товара'
        constraints = [
            models.UniqueConstraint(fields=['product', 'characteristic'], name='unique_characteristic_per_product'),
        ]

    def __str__(self):
        return f'{self.characteristic.name}: {self.value}'


MAX_PHOTOS = 10  # главное фото + до 9 дополнительных


class ProductImage(models.Model):
    """Дополнительные фото товара (галерея). Главное фото — Product.image."""

    product = models.ForeignKey(Product, verbose_name='Товар', on_delete=models.CASCADE, related_name='gallery')
    image = models.ImageField('Фото', upload_to='products/')
    position = models.PositiveSmallIntegerField('Порядок', default=0)
    created_at = models.DateTimeField('Загружено', auto_now_add=True)

    class Meta:
        verbose_name = 'Фото товара'
        verbose_name_plural = 'Фото товара'
        ordering = ['position', 'id']

    def __str__(self):
        return f'Фото {self.product}'


class Favorite(models.Model):
    """Товар в избранном у покупателя."""

    customer = models.ForeignKey('users.Customer', verbose_name='Покупатель', on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey(Product, verbose_name='Товар', on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField('Добавлено', auto_now_add=True)

    class Meta:
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['customer', 'product'], name='unique_favorite'),
        ]

    def __str__(self):
        return f'{self.customer} ♡ {self.product}'
