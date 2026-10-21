"""Кабинет продавца: свои товары, фото, характеристики, журнал склада по своим товарам."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import ProtectedError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from marketplace.fields import ActiveByDefaultField
from marketplace.permissions import CanManageProducts, IsSeller, has_role
from promotions.models import PriceCalculator
from users.models import User
from warehouse.models import StockMovement

from .filters import ArticleSearchFilter
from .models import MAX_PHOTOS, CatalogError, Category, Characteristic, Product, ProductCharacteristic, ProductImage


# ---------- Характеристики (справочник) ----------

class CharacteristicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Characteristic
        fields = ('id', 'name', 'unit')


@extend_schema_view(
    list=extend_schema(tags=['Каталог'], summary='Справочник характеристик (для фильтров и карточек)'),
    create=extend_schema(tags=['Кабинет продавца'], summary='Добавить характеристику в справочник'),
)
class CharacteristicViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = CharacteristicSerializer
    queryset = Characteristic.objects.all()
    search_fields = ['name']
    pagination_class = None

    def get_permissions(self):
        if self.action == 'list':
            return [AllowAny()]
        return [(CanManageProducts | has_role(User.Role.MANAGER))()]


# ---------- Товары продавца ----------

class ProductCharacteristicWriteSerializer(serializers.ModelSerializer):
    characteristic_id = serializers.PrimaryKeyRelatedField(queryset=Characteristic.objects.all(),
                                                           source='characteristic')
    name = serializers.CharField(source='characteristic.name', read_only=True)
    unit = serializers.CharField(source='characteristic.unit', read_only=True)

    class Meta:
        model = ProductCharacteristic
        fields = ('characteristic_id', 'name', 'unit', 'value')


class GalleryPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ('id', 'image')


class SellerProductSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category')
    characteristics = ProductCharacteristicWriteSerializer(many=True, required=False)
    is_active = ActiveByDefaultField()
    available = serializers.IntegerField(read_only=True)
    current_price = serializers.SerializerMethodField()
    in_catalog = serializers.SerializerMethodField()
    gallery = GalleryPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'article', 'name', 'description', 'category_id', 'price', 'current_price', 'is_active', 'in_catalog',
                  'image', 'gallery', 'stock', 'reserved', 'available', 'characteristics', 'created_at', 'updated_at')
        read_only_fields = ('article', 'image', 'stock', 'reserved', 'created_at', 'updated_at')

    def get_current_price(self, product) -> str:
        calculator = self.context.setdefault('price_calculator', PriceCalculator())
        return str(product.price - calculator.best(product)[1])

    def get_in_catalog(self, product) -> bool:
        """Виден ли товар покупателям: он включён и магазин одобрен."""
        return product.is_active and product.seller.is_active

    def validate_category_id(self, category):  # имя — как у поля во входных данных
        if not category.is_leaf:
            raise serializers.ValidationError('Выберите конечную категорию (без подкатегорий)')
        return category

    def validate_characteristics(self, items):
        ids = [item['characteristic'].pk for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Каждая характеристика указывается один раз')
        return items

    def _save_characteristics(self, product, items):
        if items is None:
            return  # характеристики не передали — не трогаем
        product.characteristics.all().delete()
        ProductCharacteristic.objects.bulk_create(
            ProductCharacteristic(product=product, characteristic=i['characteristic'], value=i['value'])
            for i in items
        )

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop('characteristics', [])
        product = Product.objects.create(seller=self.context['request'].user.seller, **validated_data)
        self._save_characteristics(product, items)
        return product

    @transaction.atomic
    def update(self, product, validated_data):
        items = validated_data.pop('characteristics', None)
        product = super().update(product, validated_data)
        self._save_characteristics(product, items)
        return product


def delete_file_if_unused(field_file):
    """Удалить файл фото с диска, только если на него больше никто не ссылается
    (один файл могли назначить нескольким товарам, например вручную в админке)."""
    name = field_file.name
    if name and not Product.objects.filter(image=name).exists() and not ProductImage.objects.filter(image=name).exists():
        field_file.storage.delete(name)


class ImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()


@extend_schema_view(
    list=extend_schema(tags=['Кабинет продавца'], summary='Мои товары'),
    retrieve=extend_schema(tags=['Кабинет продавца'], summary='Мой товар'),
    create=extend_schema(tags=['Кабинет продавца'], summary='Добавить товар (остаток вносит склад при поставке)'),
    partial_update=extend_schema(tags=['Кабинет продавца'], summary='Изменить товар'),
    destroy=extend_schema(tags=['Кабинет продавца'],
                          summary='Удалить товар (только если по нему ещё не было движений и заказов)'),
)
class SellerProductViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageProducts]
    serializer_class = SellerProductSerializer
    filter_backends = [DjangoFilterBackend, ArticleSearchFilter, OrderingFilter]
    http_method_names = ['get', 'post', 'patch', 'delete']
    filterset_fields = ['is_active', 'category']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'created_at', 'stock']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Product.objects.none()
        # Изоляция: только свои товары, чужой — 404
        return Product.objects.filter(seller=self.request.user.seller) \
            .select_related('seller', 'category__parent').prefetch_related('characteristics__characteristic', 'gallery')

    def perform_destroy(self, product):
        try:
            product.delete()
        except ProtectedError:
            raise CatalogError('У товара уже есть история (поставки или заказы) — удалить нельзя. '
                               'Снимите его с продажи: is_active = false')

    @extend_schema(tags=['Кабинет продавца'], summary='Загрузить фото товара', request=ImageUploadSerializer,
                   responses=SellerProductSerializer)
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def image(self, request, pk=None):
        product = self.get_object()
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # Pillow проверяет, что это действительно картинка
        old = product.image
        product.image = serializer.validated_data['image']
        product.save(update_fields=['image', 'updated_at'])
        delete_file_if_unused(old)  # старый файл — с диска, если он больше нигде не используется
        return Response(self.get_serializer(product).data)

    @extend_schema(tags=['Кабинет продавца'], summary=f'Добавить фото в галерею (несколько файлов в поле images, всего до {MAX_PHOTOS})',
                   request={'multipart/form-data': {'type': 'object', 'properties': {
                       'images': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'}}}}},
                   responses=SellerProductSerializer)
    @action(detail=True, methods=['post'], url_path='photos', parser_classes=[MultiPartParser, FormParser])
    def add_photos(self, request, pk=None):
        product = self.get_object()
        files = request.FILES.getlist('images')
        if not files:
            raise CatalogError('Выберите хотя бы одно фото')
        used = (1 if product.image else 0) + product.gallery.count()
        if used + len(files) > MAX_PHOTOS:
            raise CatalogError(f'У товара может быть не больше {MAX_PHOTOS} фото — можно добавить ещё {MAX_PHOTOS - used}')
        images = []
        for file in files:  # каждую проверяем Pillow: действительно ли это картинка
            check = ImageUploadSerializer(data={'image': file})
            if not check.is_valid():
                raise CatalogError(f'«{file.name}» — не изображение или файл повреждён')
            images.append(check.validated_data['image'])
        if not product.image:  # главного фото нет — первое загруженное становится главным
            product.image = images.pop(0)
            product.save(update_fields=['image', 'updated_at'])
        start = product.gallery.count()
        for i, image in enumerate(images):
            ProductImage.objects.create(product=product, image=image, position=start + i)
        return Response(self.get_serializer(self.get_queryset().get(pk=product.pk)).data)

    @extend_schema(tags=['Кабинет продавца'], summary='Удалить фото из галереи', responses=SellerProductSerializer)
    @action(detail=True, methods=['delete'], url_path=r'photos/(?P<photo_id>\d+)')
    def delete_photo(self, request, pk=None, photo_id=None):
        product = self.get_object()
        photo = get_object_or_404(product.gallery, pk=photo_id)
        file = photo.image
        photo.delete()
        delete_file_if_unused(file)
        return Response(self.get_serializer(self.get_queryset().get(pk=product.pk)).data)

    @extend_schema(tags=['Кабинет продавца'], summary='Сделать фото главным (меняется местами с текущим главным)',
                   request=None, responses=SellerProductSerializer)
    @action(detail=True, methods=['post'], url_path=r'photos/(?P<photo_id>\d+)/cover')
    def make_cover(self, request, pk=None, photo_id=None):
        product = self.get_object()
        photo = get_object_or_404(product.gallery, pk=photo_id)
        if product.image:
            product.image, photo.image = photo.image, product.image
            photo.save(update_fields=['image'])
        else:
            product.image = photo.image
            photo.delete()
        product.save(update_fields=['image', 'updated_at'])
        return Response(self.get_serializer(self.get_queryset().get(pk=product.pk)).data)


class StockMovementSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display')
    product_name = serializers.CharField(source='product.name')

    class Meta:
        model = StockMovement
        fields = ('id', 'product_id', 'product_name', 'type', 'type_display', 'quantity', 'stock_delta',
                  'reserved_delta', 'stock_after', 'reserved_after', 'seller_order_id', 'comment', 'created_at')


@extend_schema(tags=['Кабинет продавца'], summary='Движение моих товаров на складе')
class SellerStockMovementListView(generics.ListAPIView):
    permission_classes = [IsSeller]
    serializer_class = StockMovementSerializer
    filterset_fields = ['product', 'type']
    ordering = ['-created_at', '-id']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return StockMovement.objects.none()
        return StockMovement.objects.filter(product__seller=self.request.user.seller).select_related('product')
