"""Менеджер: одобрение продавцов. Администратор: управление пользователями (use case «Управление пользователями»)."""
from django.contrib.auth.password_validation import validate_password
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from marketplace.fields import ActiveByDefaultField
from marketplace.permissions import has_role

from .models import Seller, User

IsManager = has_role(User.Role.MANAGER)
IsAdmin = has_role()  # только администратор (has_role всегда пропускает администратора)


# ---------- Менеджер: продавцы ----------

class ManagerSellerSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email')
    login = serializers.CharField(source='user.login', read_only=True)
    owner = serializers.CharField(source='user.full_name')
    status_display = serializers.CharField(source='get_status_display')
    products_count = serializers.IntegerField(source='products.count')

    class Meta:
        model = Seller
        fields = ('id', 'store_name', 'email', 'login', 'owner', 'status', 'status_display', 'products_count')


SELLER_STATUS_TEXT = {
    'active': 'Ваш магазин одобрен — товары появились в каталоге',
    'suspended': 'Работа магазина приостановлена менеджером. Товары скрыты из каталога',
    'blocked': 'Магазин заблокирован. Товары скрыты из каталога',
}


class SellerStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Seller.STATUS_CHOICES)


@extend_schema_view(
    list=extend_schema(tags=['Менеджер'], summary='Продавцы (?status=pending — заявки на проверку)'),
    retrieve=extend_schema(tags=['Менеджер'], summary='Продавец'),
)
class ManagerSellerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsManager]
    serializer_class = ManagerSellerSerializer
    queryset = Seller.objects.select_related('user')
    filterset_fields = ['status']
    search_fields = ['store_name', 'user__email', 'user__login']
    ordering = ['store_name']

    @extend_schema(tags=['Менеджер'],
                   summary='Сменить статус: active — одобрить, suspended — приостановить, blocked — заблокировать',
                   request=SellerStatusSerializer, responses=ManagerSellerSerializer)
    @action(detail=True, methods=['post'], url_path='set-status')
    def set_status(self, request, pk=None):
        seller = self.get_object()
        serializer = SellerStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Товары не-активного продавца сразу пропадают из каталога, а новые заказы на них не оформить
        seller.status = serializer.validated_data['status']
        seller.save(update_fields=['status'])
        from notifications.models import notify  # импорт внутри: notifications зависит от users
        notify(seller.user, SELLER_STATUS_TEXT.get(seller.status, f'Статус магазина: {seller.get_status_display()}'), '/seller')
        return Response(self.get_serializer(seller).data)


# ---------- Администратор: пользователи ----------

class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})
    is_active = ActiveByDefaultField()
    has_customer_profile = serializers.SerializerMethodField()
    has_seller_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'login', 'password', 'first_name', 'last_name', 'role', 'is_active', 'date_joined',
                  'last_login', 'has_customer_profile', 'has_seller_profile')
        read_only_fields = ('date_joined', 'last_login')

    def get_has_customer_profile(self, user) -> bool:
        return hasattr(user, 'customer')

    def get_has_seller_profile(self, user) -> bool:
        return hasattr(user, 'seller')

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_login(self, login):
        # Без учёта регистра, как и при регистрации: «Ivan» и «ivan» — один логин
        if login and User.objects.filter(login__iexact=login).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError('Этот логин уже занят')
        return login or None

    def validate(self, data):
        email = data.get('email', getattr(self.instance, 'email', None))
        login = data.get('login', getattr(self.instance, 'login', None))
        if not email and not login:
            message = 'Укажите email или логин'
            raise serializers.ValidationError({'email': message, 'login': message})
        if self.instance is None and not data.get('password'):
            raise serializers.ValidationError({'password': 'Задайте пароль новому сотруднику'})
        # Покупателей и продавцов создают через регистрацию — у них есть профили; здесь — только персонал
        role = data.get('role')
        if self.instance is None and role in (User.Role.CUSTOMER, User.Role.SELLER):
            raise serializers.ValidationError({'role': 'Покупатели и продавцы регистрируются сами'})
        request = self.context['request']
        if self.instance == request.user and ('role' in data or data.get('is_active') is False):
            raise serializers.ValidationError('Нельзя менять роль или блокировать самого себя')
        return data

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

    def update(self, user, validated_data):
        password = validated_data.pop('password', None)
        user = super().update(user, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=['password'])
        return user


@extend_schema_view(
    list=extend_schema(tags=['Администратор'], summary='Пользователи'),
    retrieve=extend_schema(tags=['Администратор'], summary='Пользователь'),
    create=extend_schema(tags=['Администратор'], summary='Создать сотрудника (курьер, склад, ПВЗ, менеджер…)'),
    partial_update=extend_schema(tags=['Администратор'],
                                 summary='Изменить: роль, имя, пароль; is_active=false — заблокировать вход'),
)
class AdminUserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                       mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Удаления нет: у пользователей есть история (заказы, операции) — вместо удаления блокировка."""
    permission_classes = [IsAdmin]
    serializer_class = AdminUserSerializer
    queryset = User.objects.select_related('customer', 'seller')
    http_method_names = ['get', 'post', 'patch']
    filterset_fields = ['role', 'is_active']
    search_fields = ['email', 'login', 'first_name', 'last_name']
    ordering = ['id']  # не по email: у части пользователей его нет
