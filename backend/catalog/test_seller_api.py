import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from marketplace.testing import auth, make_product, make_seller

from .models import Category, Characteristic

TEMP_MEDIA = tempfile.mkdtemp()


def png_file(name='photo.png'):
    buffer = BytesIO()
    Image.new('RGB', (10, 10), 'red').save(buffer, 'PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)  # тестовые фото не попадают в настоящую папку media
class SellerProductApiTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.meds = Category.objects.create(name='Лекарства', slug='meds')
        self.spray = self.meds.add_subcategory('Спреи', 'spray')
        self.volume = Characteristic.objects.create(name='Объём', unit='мл')
        self.seller = make_seller()
        auth(self.client, self.seller)

    def create(self, **data):
        payload = {'name': 'Спрей', 'category_id': self.spray.pk, 'price': '250.00', **data}
        return self.client.post('/api/seller/products/', payload, format='json')

    def test_create_with_characteristics(self):
        r = self.create(characteristics=[{'characteristic_id': self.volume.pk, 'value': '20'}])
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['stock'], 0)  # остаток появляется только после поставки на склад
        self.assertEqual(r.data['characteristics'][0]['name'], 'Объём')
        self.assertTrue(r.data['in_catalog'])

    def test_category_must_be_leaf_and_stock_not_writable(self):
        r = self.create(category_id=self.meds.pk)
        self.assertEqual(r.status_code, 400)
        self.assertIn('category_id', r.data)
        r = self.create(stock=1000)
        self.assertEqual(r.data['stock'], 0)

    def test_update_replaces_characteristics(self):
        product_id = self.create(characteristics=[{'characteristic_id': self.volume.pk, 'value': '20'}]).data['id']
        country = Characteristic.objects.create(name='Страна')
        r = self.client.patch(f'/api/seller/products/{product_id}/', {
            'price': '199.90', 'characteristics': [{'characteristic_id': country.pk, 'value': 'Россия'}],
        }, format='json')
        self.assertEqual(r.data['price'], '199.90')
        self.assertEqual([c['name'] for c in r.data['characteristics']], ['Страна'])

    def test_image_upload(self):
        product_id = self.create().data['id']
        r = self.client.post(f'/api/seller/products/{product_id}/image/', {'image': png_file()}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('/media/products/', r.data['image'])
        not_image = SimpleUploadedFile('virus.png', b'not an image', content_type='image/png')
        r = self.client.post(f'/api/seller/products/{product_id}/image/', {'image': not_image}, format='multipart')
        self.assertEqual(r.status_code, 400)

    def test_isolation_from_other_sellers(self):
        foreign = make_product(make_seller('other@test.ru', 'Чужой'), name='Чужой товар')
        self.assertEqual(self.client.get('/api/seller/products/').data['count'], 0)
        self.assertEqual(self.client.patch(f'/api/seller/products/{foreign.pk}/', {'price': '1'}).status_code, 404)
        self.assertEqual(self.client.delete(f'/api/seller/products/{foreign.pk}/').status_code, 404)

    def test_delete_only_without_history(self):
        fresh_id = self.create().data['id']
        self.assertEqual(self.client.delete(f'/api/seller/products/{fresh_id}/').status_code, 204)
        stocked = make_product(self.seller, self.spray, stock=5)  # есть приход на склад
        r = self.client.delete(f'/api/seller/products/{stocked.pk}/')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Снимите его с продажи', r.data['detail'])

    def test_pending_seller_prepares_products_but_not_in_catalog(self):
        pending = make_seller('new@test.ru', 'Новый', status='pending')
        auth(self.client, pending)
        r = self.create()
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data['in_catalog'])
        self.assertEqual(self.client.get('/api/products/').data['count'], 0)
        self.assertEqual(self.client.get('/api/seller/orders/').status_code, 403)  # заказы — только одобренным

    def test_blocked_seller_cannot_manage(self):
        auth(self.client, make_seller('bad@test.ru', 'Плохой', status='blocked'))
        self.assertEqual(self.create().status_code, 403)

    def test_stock_journal_only_own_products(self):
        make_product(self.seller, self.spray, stock=7)
        make_product(make_seller('other@test.ru', 'Чужой'), stock=3)
        r = self.client.get('/api/seller/stock-movements/')
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['stock_delta'], 7)
