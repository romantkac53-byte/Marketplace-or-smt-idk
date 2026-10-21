import re

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

# Логин: латиница, цифры, точка, дефис, подчёркивание. Без «@» — так логин никогда не спутать с email
LOGIN_RE = r'^[A-Za-z0-9_.-]{3,30}$'
login_validator = RegexValidator(
    LOGIN_RE, 'Логин: от 3 до 30 символов — латинские буквы, цифры, точка, дефис или подчёркивание')


def validate_phone(value):
    """Телефон: цифры, пробелы, скобки, дефисы, «+» в начале; всего 10–15 цифр. Пустой — допустим."""
    if not value:
        return
    digits = sum(ch.isdigit() for ch in value)
    if not re.fullmatch(r'\+?[\d\s()\-]+', value) or not 10 <= digits <= 15:
        raise ValidationError('Введите телефон цифрами, например +7 900 123-45-67 (от 10 до 15 цифр)')


class UserManager(BaseUserManager):
    """Создание пользователей: по email, по логину или по обоим сразу."""

    use_in_migrations = True

    def _create_user(self, email, password, login=None, **extra_fields):
        if not email and not login:
            raise ValueError('Нужен email или логин')
        # Пустая строка -> NULL: у многих пользователей нет email (или логина), а уникальность NULL не нарушает
        email = self.normalize_email(email) or None
        user = self.model(email=email, login=login or None, **extra_fields)
        user.set_password(password)  # пароль хранится только в виде хэша
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    # Гость — это неавторизованный посетитель, поэтому в базе его нет.
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Покупатель'
        SELLER = 'seller', 'Продавец'
        MANAGER = 'manager', 'Менеджер'
        WAREHOUSE = 'warehouse', 'Сотрудник склада'
        COURIER = 'courier', 'Курьер'
        PICKUP = 'pickup', 'Сотрудник ПВЗ'
        ADMIN = 'admin', 'Администратор'
        DIRECTOR = 'director', 'Руководитель'

    username = None  # вместо username — email и/или логин
    # Email и логин необязательны по отдельности, но хотя бы одно из них есть всегда (проверяют регистрация и менеджер)
    email = models.EmailField('Email', unique=True, null=True, blank=True)
    login = models.CharField('Логин', max_length=30, unique=True, null=True, blank=True,
                             validators=[login_validator], help_text='Для входа без email')
    role = models.CharField('Роль', max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    # Когда принял пользовательское соглашение (при регистрации). У сотрудников, созданных админом, — пусто
    terms_accepted_at = models.DateTimeField('Соглашение принято', null=True, blank=True)

    USERNAME_FIELD = 'email'  # для createsuperuser; вход по логину — в users/backends.py
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.identifier

    def save(self, *args, **kwargs):
        # Из форм может прийти пустая строка — храним NULL, иначе два «пустых» email конфликтуют по уникальности
        self.email = self.email or None
        self.login = self.login or None
        super().save(*args, **kwargs)

    @property
    def identifier(self) -> str:
        """То, по чему пользователь входит: email, а если его нет — логин."""
        return self.email or self.login or f'Пользователь #{self.pk}'

    @property
    def full_name(self) -> str:
        return self.get_full_name() or self.identifier

    @property
    def public_name(self) -> str:
        """Имя для чужих глаз (отзывы): имя, иначе логин, иначе начало email — но не email целиком."""
        return self.first_name or self.login or (self.email or '').split('@')[0]


class Customer(models.Model):
    user = models.OneToOneField(User, verbose_name='Пользователь', on_delete=models.CASCADE, related_name='customer')
    phone = models.CharField('Телефон', max_length=20, blank=True, validators=[validate_phone])
    address = models.CharField('Адрес доставки', max_length=255, blank=True)
    # Меняется только через payments.models.change_balance — так каждое движение попадает в журнал
    balance = models.DecimalField('Баланс', max_digits=12, decimal_places=2, default=0, editable=False)

    class Meta:
        verbose_name = 'Покупатель'
        verbose_name_plural = 'Покупатели'

    def __str__(self):
        return self.user.full_name

    def add_to_cart(self, product, quantity=1):
        """addToCart() с диаграммы: добавляет товар в корзину покупателя."""
        from cart.models import Cart

        cart, _ = Cart.objects.get_or_create(customer=self)
        return cart.add_product(product, quantity)

    def place_order(self, delivery_address='', pickup_point=None):
        """placeOrder() с диаграммы: оформляет заказ из корзины (курьером или в ПВЗ)."""
        from orders.models import place_order

        return place_order(self, delivery_address, pickup_point)

    def leave_review(self, product, rating, text=''):
        """«Оставление отзыва» из use case."""
        from reviews.models import leave_review

        return leave_review(self, product, rating, text)

    def request_return(self, order_item, quantity, reason, description=''):
        """Заявка на возврат полученного товара."""
        from returns.models import request_return

        return request_return(self, order_item, quantity, reason, description)


class Seller(models.Model):
    STATUS_CHOICES = [
        ('pending', 'На проверке'),
        ('active', 'Активен'),
        ('suspended', 'Приостановлен'),
        ('blocked', 'Заблокирован'),
    ]
    user = models.OneToOneField(User, verbose_name='Пользователь', on_delete=models.CASCADE, related_name='seller')
    store_name = models.CharField('Название магазина', max_length=100)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        verbose_name = 'Продавец'
        verbose_name_plural = 'Продавцы'

    def __str__(self):
        return self.store_name

    @property
    def is_active(self):
        # Продавать могут только одобренные продавцы
        return self.status == 'active'
