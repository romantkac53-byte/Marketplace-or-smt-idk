"""Поиск без учёта регистра для кириллицы в SQLite.

Встроенный LIKE в SQLite игнорирует регистр только у латиницы: «спрей» не находит «Спрей».
Django делает через LIKE поиск (?search=), фильтры icontains/iexact — значит, поиск по-русски
в разработке не работал бы. Подменяем функцию like() в SQLite на версию на Python, которая
сравнивает строки через casefold(). В PostgreSQL (ILIKE) этой проблемы нет — там код не включается.
"""
import re
from functools import lru_cache

from django.db.backends.signals import connection_created


@lru_cache(maxsize=512)
def _compile(pattern, escape):
    regex, i = [], 0
    while i < len(pattern):
        char = pattern[i]
        if escape and char == escape and i + 1 < len(pattern):
            regex.append(re.escape(pattern[i + 1]))  # экранированный % или _ — обычный символ
            i += 2
            continue
        regex.append('.*' if char == '%' else '.' if char == '_' else re.escape(char))
        i += 1
    return re.compile(''.join(regex), re.DOTALL)


def _like(pattern, value, escape=None):
    """Аргументы — как у like() в SQLite: like(шаблон, строка[, символ_экранирования])."""
    if pattern is None or value is None:
        return None
    return _compile(pattern.casefold(), escape).fullmatch(str(value).casefold()) is not None


def _register(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        connection.connection.create_function('like', 2, _like, deterministic=True)
        connection.connection.create_function('like', 3, _like, deterministic=True)


def enable():
    connection_created.connect(_register, dispatch_uid='sqlite_unicode_like')
