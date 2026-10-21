"""Резервная копия данных в JSON (UTF-8), которую можно восстановить командой loaddata.

    python manage.py backup                 → backend/backups/backup_ГГГГ-ММ-ДД_ЧЧ-ММ.json
    python manage.py backup путь/к/файлу.json
    Восстановление: python manage.py loaddata путь/к/файлу.json   (в базу после migrate)
"""
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.utils import timezone

# Служебные таблицы: создаются заново при migrate (права, типы) или не нужны в копии (сессии, токены, журнал админки)
EXCLUDE = ['contenttypes', 'auth.permission', 'admin.logentry', 'sessions', 'token_blacklist']


class Command(BaseCommand):
    help = 'Резервная копия базы в JSON (UTF-8). Восстановление: python manage.py loaddata <файл>'

    def add_arguments(self, parser):
        parser.add_argument('path', nargs='?', help='Куда сохранить (по умолчанию backups/backup_<дата>.json)')

    def handle(self, *args, path=None, **options):
        if path:
            path = Path(path)
        else:
            folder = Path(settings.BASE_DIR) / 'backups'
            folder.mkdir(exist_ok=True)
            path = folder / f'backup_{timezone.localtime():%Y-%m-%d_%H-%M}.json'
        # Кодировку задаём явно: стандартный «dumpdata -o файл» пишет в кодировке системы
        # (в русской Windows — cp1251), а loaddata читает только UTF-8 — такую копию не восстановить
        with path.open('w', encoding='utf-8') as stream:
            call_command('dumpdata', exclude=EXCLUDE, indent=1, stdout=stream)
        self.stdout.write(self.style.SUCCESS(f'Резервная копия сохранена: {path} ({path.stat().st_size // 1024} КБ)'))
