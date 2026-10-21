from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'users'
    verbose_name = 'Пользователи'

    def ready(self):
        # Служебные таблицы JWT (выданные и отозванные токены) ведёт библиотека simplejwt автоматически —
        # администратору они не нужны, а их подписи только по-английски. Убираем их из админ-панели.
        from django.contrib import admin
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
        for model in (OutstandingToken, BlacklistedToken):
            if admin.site.is_registered(model):
                admin.site.unregister(model)
