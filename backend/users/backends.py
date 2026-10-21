from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrLoginBackend(ModelBackend):
    """Вход по email или по логину — что пользователь ввёл, то и ищем (без учёта регистра).

    Логин не может содержать «@», а email всегда содержит — поэтому одна строка не совпадёт с двумя разными людьми.
    Работает и для API (/api/auth/login/), и для входа в админку.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        identifier = (username or kwargs.get(User.USERNAME_FIELD) or kwargs.get('login') or '').strip()
        if not identifier or password is None:
            return None
        field = 'email__iexact' if '@' in identifier else 'login__iexact'
        user = User.objects.filter(**{field: identifier}).first()
        if user is None:
            User().set_password(password)  # тратим столько же времени, сколько на проверку — не выдаём, есть ли такой
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
