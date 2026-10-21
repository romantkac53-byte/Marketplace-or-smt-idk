"""Регрессионные тесты к дефектам, найденным при тестировании на соответствие ТЗ (лабораторная работа №8)."""
import re
import tempfile
from pathlib import Path

from django.apps import apps
from django.contrib import admin
from django.core.management import call_command
from rest_framework.test import APITestCase

from catalog.models import Category
from users.models import User

from .testing import PASSWORD, auth, make_customer, make_seller

OUR_APPS = ['users', 'catalog', 'cart', 'orders', 'payments', 'delivery', 'warehouse', 'reviews', 'returns',
            'promotions', 'reports', 'notifications']


class AdminInRussianTests(APITestCase):
    """BUG-01: интерфейс административной панели на русском языке (ТЗ: русский язык интерфейса)."""

    def test_app_and_field_labels_are_russian(self):
        for label in OUR_APPS:
            config = apps.get_app_config(label)
            self.assertRegex(str(config.verbose_name), '[А-Яа-я]', label)
            for model in config.get_models():
                for field in model._meta.get_fields():
                    if getattr(field, 'concrete', False) and not field.auto_created:
                        # Подпись не должна быть сгенерирована из имени поля («store name», «created at»)
                        self.assertNotEqual(str(field.verbose_name), field.name.replace('_', ' '),
                                            f'{model._meta.label}.{field.name}')

    def test_jwt_service_tables_hidden(self):
        registered = {m._meta.label for m in admin.site._registry}
        self.assertNotIn('token_blacklist.OutstandingToken', registered)
        self.assertNotIn('token_blacklist.BlacklistedToken', registered)

    def test_admin_pages_have_no_english_labels(self):
        User.objects.create_superuser(email='root@test.ru', password=PASSWORD)
        self.client.login(username='root@test.ru', password=PASSWORD)
        page = self.client.get('/admin/').content.decode()
        captions = re.findall(r'<caption>\s*<a[^>]*>(.*?)</a>', page, re.S)
        self.assertTrue(captions)
        self.assertFalse([c for c in captions if re.fullmatch(r'[A-Za-z ]+', c.strip())], captions)
        # Пустой вариант выпадающих списков (строка Django 6.1 без русского перевода — переведена в backend/locale)
        form = self.client.get('/admin/catalog/product/add/').content.decode()
        self.assertNotIn('Select an option', form)
        self.assertIn('Выберите вариант', form)


class PermissionMessageTests(APITestCase):
    """BUG-02: покупателю, открывшему раздел продавца, — «Доступно только продавцам», а не про статус магазина."""

    def test_customer_gets_sellers_only_message(self):
        auth(self.client, make_customer())
        for url in ('/api/seller/products/', '/api/seller/orders/'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.data['detail'], 'Доступно только продавцам')

    def test_store_status_messages_kept(self):
        auth(self.client, make_seller(status='blocked'))
        self.assertEqual(self.client.get('/api/seller/products/').data['detail'], 'Магазин приостановлен или заблокирован')
        self.assertEqual(self.client.get('/api/seller/orders/').data['detail'], 'Магазин ещё не одобрен или заблокирован')


class PhoneValidationTests(APITestCase):
    """BUG-03: телефон — только цифры и знаки + ( ) - пробел, от 10 до 15 цифр."""

    def register(self, phone):
        return self.client.post('/api/auth/register/customer/', {
            'email': f'p{abs(hash(phone)) % 10000}@test.ru', 'password': PASSWORD, 'accept_terms': True, 'phone': phone,
        }, format='json')

    def test_invalid_phones_rejected(self):
        for phone in ('abc', '12', 'телефон', '+7 900 123-45-67 доб. 5'):
            r = self.register(phone)
            self.assertEqual(r.status_code, 400, phone)
            self.assertIn('phone', r.data)

    def test_valid_phones_accepted(self):
        for phone in ('+7 (900) 123-45-67', '89001234567', '', '+44 20 7946 0958'):
            self.assertEqual(self.register(phone).status_code, 201, phone)

    def test_profile_update_checks_phone(self):
        auth(self.client, make_customer())
        r = self.client.patch('/api/me/', {'customer': {'phone': 'abc'}}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('phone', r.data['customer'])


class NotFoundInRussianTests(APITestCase):
    """BUG-04: «не найдено» — по-русски, без английского текста Django и имени модели."""

    def test_missing_and_foreign_order(self):
        auth(self.client, make_customer())
        r = self.client.get('/api/orders/99999/')
        self.assertEqual(r.status_code, 404)
        self.assertNotRegex(r.data['detail'], '[A-Za-z]')
        self.assertIn('Не найдено', r.data['detail'])


class BackupTests(APITestCase):
    """BUG-05: резервная копия в UTF-8 восстанавливается командой loaddata (в том числе в русской Windows)."""

    def test_backup_is_utf8_and_restorable(self):
        Category.objects.create(name='Овощи и фрукты', slug='veg-fruit')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'backup.json'
            call_command('backup', str(path), stdout=open(Path(tmp) / 'out.txt', 'w', encoding='utf-8'))
            text = path.read_bytes().decode('utf-8')  # не должно падать — файл в UTF-8
            self.assertIn('Овощи и фрукты', text)
            Category.objects.all().delete()
            call_command('loaddata', str(path), verbosity=0)
        self.assertTrue(Category.objects.filter(name='Овощи и фрукты').exists())
