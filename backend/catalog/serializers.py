from rest_framework import serializers

from promotions.models import PriceCalculator
from reviews.models import Review

from .models import Category, Product, ProductCharacteristic


class CategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug')


class CategoryTreeSerializer(serializers.Serializer):
    """Только для документации: узел дерева категорий (children — такие же узлы)."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    children = serializers.ListField(child=serializers.DictField())


class ProductPriceMixin(serializers.Serializer):
    """Цена со скидкой. Калькулятор акций берётся из контекста — один на весь список."""

    current_price = serializers.SerializerMethodField()
    promotion = serializers.SerializerMethodField()

    def _best(self, product):
        calculator = self.context.get('price_calculator') or PriceCalculator()
        cache = self.context.setdefault('_best_cache', {})
        if product.pk not in cache:
            cache[product.pk] = calculator.best(product)
        return cache[product.pk]

    def get_current_price(self, product) -> str:
        promotion, discount = self._best(product)
        return str(product.price - discount)

    def get_promotion(self, product) -> str | None:
        promotion, _ = self._best(product)
        return str(promotion) if promotion else None


class ProductListSerializer(ProductPriceMixin, serializers.ModelSerializer):
    """Карточка товара в списке каталога."""

    seller = serializers.CharField(source='seller.store_name')
    seller_id = serializers.IntegerField()
    category = CategoryBriefSerializer()
    available = serializers.IntegerField(read_only=True)  # свойство модели: остаток минус резерв
    rating = serializers.SerializerMethodField()
    reviews_count = serializers.IntegerField(read_only=True)
    sold_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'article', 'name', 'image', 'price', 'current_price', 'promotion', 'available', 'rating',
                  'reviews_count', 'sold_count', 'seller', 'seller_id', 'category')

    def get_rating(self, product) -> float | None:
        avg = getattr(product, 'rating_avg', None)
        return round(avg, 1) if avg is not None else None


class ProductCharacteristicSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='characteristic.id')
    name = serializers.CharField(source='characteristic.name')
    unit = serializers.CharField(source='characteristic.unit')

    class Meta:
        model = ProductCharacteristic
        fields = ('id', 'name', 'unit', 'value')


class ProductDetailSerializer(ProductListSerializer):
    """Страница товара: всё из списка + описание, путь категории, характеристики."""

    category_path = serializers.SerializerMethodField()
    characteristics = ProductCharacteristicSerializer(many=True)
    images = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ('description', 'category_path', 'characteristics', 'images')

    def get_images(self, product) -> list[str]:
        """Все фото для галереи: сначала главное, потом дополнительные по порядку."""
        request = self.context.get('request')
        files = ([product.image] if product.image else []) + [photo.image for photo in product.gallery.all()]
        return [request.build_absolute_uri(f.url) if request else f.url for f in files]

    def get_category_path(self, product) -> list[dict]:
        """Хлебные крошки: Лекарства → Спреи."""
        return CategoryBriefSerializer(product.category.get_ancestors(include_self=True), many=True).data


class PublicReviewSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ('id', 'author', 'rating', 'text', 'seller_reply', 'replied_at', 'created_at')

    def get_author(self, review) -> str:
        # Публично показываем только имя (или логин / начало email), а не полные данные покупателя
        user = review.customer.user
        return user.public_name
