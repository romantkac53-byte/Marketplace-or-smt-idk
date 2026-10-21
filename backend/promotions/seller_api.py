"""Кабинет продавца: акции своего магазина."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, viewsets

from catalog.models import Category, Product
from marketplace.fields import ActiveByDefaultField
from marketplace.permissions import IsActiveSeller, has_role
from users.models import Seller, User

from .models import Promotion


class SellerPromotionSerializer(serializers.ModelSerializer):
    product_ids = serializers.PrimaryKeyRelatedField(source='products', many=True, required=False,
                                                     queryset=Product.objects.all())
    category_ids = serializers.PrimaryKeyRelatedField(source='categories', many=True, required=False,
                                                      queryset=Category.objects.all())
    is_running = serializers.BooleanField(read_only=True)
    is_active = ActiveByDefaultField()

    class Meta:
        model = Promotion
        fields = ('id', 'name', 'discount_type', 'value', 'starts_at', 'ends_at', 'is_active', 'is_running',
                  'product_ids', 'category_ids', 'created_at')
        read_only_fields = ('created_at',)
        extra_kwargs = {'starts_at': {'required': False, 'help_text': 'Пусто — акция начнётся сразу'}}

    def validate_product_ids(self, products):
        seller = self.context['request'].user.seller
        foreign = [p.pk for p in products if p.seller_id != seller.pk]
        if foreign:
            raise serializers.ValidationError(f'Это не ваши товары: {foreign}')
        return products

    def validate(self, data):
        # Начало не указано — «сразу», по часам сервера (часы у пользователя могут спешить)
        if self.instance is None and not data.get('starts_at'):
            data['starts_at'] = timezone.now()
        # Проверки из модели (процент < 100, окончание позже начала) — на объекте с новыми значениями
        instance = Promotion(**{k: v for k, v in data.items() if k not in ('products', 'categories')})
        if self.instance:
            for field in ('discount_type', 'value', 'starts_at', 'ends_at'):
                if field not in data:
                    setattr(instance, field, getattr(self.instance, field))
        try:
            instance.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        return data

    def create(self, validated_data):
        # Акция продавца всегда привязана к его магазину — скидка только на его товары
        validated_data['seller'] = self.context['request'].user.seller
        return super().create(validated_data)


@extend_schema_view(
    list=extend_schema(tags=['Кабинет продавца'], summary='Мои акции'),
    retrieve=extend_schema(tags=['Кабинет продавца'], summary='Моя акция'),
    create=extend_schema(tags=['Кабинет продавца'],
                         summary='Создать акцию (без товаров и категорий — на все мои товары)'),
    partial_update=extend_schema(tags=['Кабинет продавца'], summary='Изменить акцию'),
    destroy=extend_schema(tags=['Кабинет продавца'], summary='Удалить акцию'),
)
class SellerPromotionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsActiveSeller]
    serializer_class = SellerPromotionSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']
    filterset_fields = ['is_active']
    ordering = ['-starts_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Promotion.objects.none()
        return Promotion.objects.filter(seller=self.request.user.seller).prefetch_related('products', 'categories')


# ---------- Менеджер: акции всей площадки ----------

class ManagerPromotionSerializer(SellerPromotionSerializer):
    seller_id = serializers.PrimaryKeyRelatedField(queryset=Seller.objects.all(), source='seller', required=False,
                                                   allow_null=True,
                                                   help_text='Пусто — акция всей площадки на любые товары')

    class Meta(SellerPromotionSerializer.Meta):
        fields = SellerPromotionSerializer.Meta.fields + ('seller_id',)

    def validate_product_ids(self, products):
        return products  # менеджер выбирает любые товары; согласованность с продавцом — в validate()

    def validate(self, data):
        data = super().validate(data)
        seller = data.get('seller', getattr(self.instance, 'seller', None))
        products = data.get('products', [])
        if seller and any(p.seller_id != seller.pk for p in products):
            raise serializers.ValidationError({'product_ids': 'Акция продавца — только на его товары'})
        return data

    def create(self, validated_data):
        return serializers.ModelSerializer.create(self, validated_data)  # продавца не подставляем


@extend_schema_view(
    list=extend_schema(tags=['Менеджер'], summary='Все акции (площадки и продавцов)'),
    retrieve=extend_schema(tags=['Менеджер'], summary='Акция'),
    create=extend_schema(tags=['Менеджер'], summary='Создать акцию площадки'),
    partial_update=extend_schema(tags=['Менеджер'], summary='Изменить акцию (например, выключить)'),
    destroy=extend_schema(tags=['Менеджер'], summary='Удалить акцию'),
)
class ManagerPromotionViewSet(viewsets.ModelViewSet):
    permission_classes = [has_role(User.Role.MANAGER)]
    serializer_class = ManagerPromotionSerializer
    queryset = Promotion.objects.prefetch_related('products', 'categories')
    http_method_names = ['get', 'post', 'patch', 'delete']
    filterset_fields = ['is_active', 'seller']
    ordering = ['-starts_at']
