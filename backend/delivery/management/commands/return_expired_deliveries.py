from django.core.management.base import BaseCommand

from delivery.models import Delivery


class Command(BaseCommand):
    help = 'Возвращает на склад посылки, которые не забрали из пункта выдачи до конца срока хранения'

    def handle(self, *args, **options):
        count = Delivery.return_expired()
        self.stdout.write(self.style.SUCCESS(f'Возвращено просроченных посылок: {count}'))
