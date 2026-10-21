from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Customer, Seller, User, login_validator, validate_phone


def tokens_for(user):
    """Пара JWT-токенов: access — для запросов (30 мин), refresh — чтобы получить новый access (7 дней)."""
    refresh = RefreshToken.for_user(user)
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


class LoginSerializer(TokenObtainPairSerializer):
    """Вход: {"email": ..., "password": ...} или {"login": ..., "password": ...} → пара токенов."""

    login = serializers.CharField(required=False, help_text='Логин — если входите не по email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.username_field].required = False  # email теперь не обязателен — можно логин

    def validate(self, attrs):
        identifier = (attrs.get(self.username_field) or attrs.pop('login', '') or '').strip()
        if not identifier:
            raise serializers.ValidationError({'login': 'Укажите email или логин'})
        attrs[self.username_field] = identifier  # дальше стандартная проверка simplejwt → users/backends.py
        return super().validate(attrs)


def validate_unique_login(login):
    """Логин свободен? (без учёта регистра: «Ivan» и «ivan» — один и тот же логин)"""
    if login and User.objects.filter(login__iexact=login).exists():
        raise serializers.ValidationError('Этот логин уже занят')
    return login


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ('phone', 'address', 'balance')
        read_only_fields = ('balance',)  # баланс меняется только пополнением/оплатой


class SellerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seller
        fields = ('store_name', 'status')
        read_only_fields = ('status',)  # статус меняет администратор


class MeSerializer(serializers.ModelSerializer):
    """Профиль текущего пользователя (личный кабинет)."""

    customer = CustomerProfileSerializer(required=False)
    seller = SellerProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ('id', 'email', 'login', 'first_name', 'last_name', 'full_name', 'role', 'customer', 'seller')
        read_only_fields = ('id', 'email', 'login', 'full_name', 'role')

    def to_representation(self, user):
        data = super().to_representation(user)
        # Показываем только тот профиль, который есть у пользователя
        if not hasattr(user, 'customer'):
            data.pop('customer')
        if not hasattr(user, 'seller'):
            data.pop('seller')
        return data

    @transaction.atomic
    def update(self, user, validated_data):
        customer_data = validated_data.pop('customer', None)
        seller_data = validated_data.pop('seller', None)
        for field, value in validated_data.items():
            setattr(user, field, value)
        user.save()
        if customer_data and hasattr(user, 'customer'):
            for field, value in customer_data.items():
                setattr(user.customer, field, value)
            user.customer.save()
        if seller_data and hasattr(user, 'seller'):
            for field, value in seller_data.items():
                setattr(user.seller, field, value)
            user.seller.save()
        return user


class _RegisterSerializer(serializers.Serializer):
    # Нужен email ИЛИ логин (можно оба) — регистрироваться без почты, например для проверки сайта
    email = serializers.EmailField(required=False, allow_blank=True)
    login = serializers.CharField(required=False, allow_blank=True, max_length=30,
                                  validators=[login_validator, validate_unique_login])
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    accept_terms = serializers.BooleanField(write_only=True, help_text='Согласие с пользовательским соглашением — обязательно')

    def validate_accept_terms(self, value):
        # Проверяем на сервере: галочку во фронтенде можно обойти, отправив запрос напрямую
        if value is not True:
            raise serializers.ValidationError('Чтобы зарегистрироваться, примите пользовательское соглашение')
        return value

    def validate(self, data):
        if not data.get('email') and not data.get('login'):
            message = 'Укажите email или логин'
            raise serializers.ValidationError({'email': message, 'login': message})
        return data

    def validate_email(self, email):
        email = User.objects.normalize_email(email)
        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('Пользователь с таким email уже зарегистрирован')
        return email

    def validate_password(self, password):
        validate_password(password)  # стандартные проверки Django: длина, не слишком простой и т.д.
        return password

    def _create_user(self, role):
        data = self.validated_data
        return User.objects.create_user(
            email=data.get('email'), login=data.get('login'), password=data['password'], role=role,
            first_name=data.get('first_name', ''), last_name=data.get('last_name', ''),
            terms_accepted_at=timezone.now(),  # фиксируем, когда пользователь согласился
        )

    def to_representation(self, user):
        return {'user': MeSerializer(user).data, 'tokens': tokens_for(user)}


class CustomerRegisterSerializer(_RegisterSerializer):
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, validators=[validate_phone])
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)

    @transaction.atomic
    def create(self, validated_data):
        user = self._create_user(User.Role.CUSTOMER)
        Customer.objects.create(user=user, phone=validated_data.get('phone', ''),
                                address=validated_data.get('address', ''))
        return user


class SellerRegisterSerializer(_RegisterSerializer):
    store_name = serializers.CharField(max_length=100)

    @transaction.atomic
    def create(self, validated_data):
        user = self._create_user(User.Role.SELLER)
        # Новый магазин — «На проверке»: продавать сможет после одобрения администратором
        Seller.objects.create(user=user, store_name=validated_data['store_name'])
        return user


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Неверный текущий пароль')
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context['request'].user)
        return value
