from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = 'catalog'
    verbose_name = 'Каталог'

    def ready(self):
        # Поиск по каталогу без учёта регистра для кириллицы, пока база — SQLite
        from marketplace import sqlite_unicode

        sqlite_unicode.enable()
