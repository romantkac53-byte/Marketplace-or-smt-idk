"""Избранное, галерея фото, фильтр ?ids= (для «Вы недавно смотрели»)."""
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from marketplace.testing import auth, make_customer, make_product, make_seller

from .models import MAX_PHOTOS
from .test_seller_api import png_file

TEMP_MEDIA = tempfile.mkdtemp()


class FavoritesTests(APITestCase):
    def setUp(self):
        self.shop = make_seller()
        self.a = make_product(self.shop, name='A')
        self.b = make_product(self.shop, name='B')
        auth(self.client, make_customer())

    def test_add_list_remove(self):
        self.assertEqual(self.client.post('/api/favorites/', {'product_id': self.a.pk}).status_code, 201)
        self.client.post('/api/favorites/', {'product_id': self.a.pk})  # повторно — без дублей
        self.client.post('/api/favorites/', {'product_id': self.b.pk})
        self.assertEqual(sorted(self.client.get('/api/favorites/ids/').data), sorted([self.a.pk, self.b.pk]))
        self.assertEqual([p['name'] for p in self.client.get('/api/favorites/').data], ['B', 'A'])  # новые сверху
        self.assertEqual(self.client.delete(f'/api/favorites/{self.a.pk}/').status_code, 204)
        self.assertEqual(self.client.get('/api/favorites/ids/').data, [self.b.pk])

    def test_hidden_product_not_listed(self):
        self.client.post('/api/favorites/', {'product_id': self.a.pk})
        self.a.is_active = False
        self.a.save()
        self.assertEqual(self.client.get('/api/favorites/').data, [])

    def test_only_customers(self):
        auth(self.client, self.shop)
        self.assertEqual(self.client.get('/api/favorites/').status_code, 403)

    def test_ids_filter(self):
        r = self.client.get('/api/products/', {'ids': f'{self.a.pk},{self.b.pk}'})
        self.assertEqual(r.data['count'], 2)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)  # тестовые фото — во временную папку, не в настоящую media
class GalleryTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.shop = make_seller()
        self.product = make_product(self.shop, name='Товар')
        auth(self.client, self.shop)
        self.url = f'/api/seller/products/{self.product.pk}/photos/'

    def test_first_upload_becomes_cover_rest_gallery(self):
        r = self.client.post(self.url, {'images': [png_file('1.png'), png_file('2.png'), png_file('3.png')]},
                             format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['image'])
        self.assertEqual(len(r.data['gallery']), 2)
        detail = self.client.get(f'/api/products/{self.product.pk}/').data
        self.assertEqual(len(detail['images']), 3)

    def test_make_cover_swaps_and_delete(self):
        data = self.client.post(self.url, {'images': [png_file('1.png'), png_file('2.png')]}, format='multipart').data
        cover, photo = data['image'], data['gallery'][0]
        r = self.client.post(f'{self.url}{photo["id"]}/cover/')
        self.assertEqual(r.data['image'], photo['image'])
        self.assertEqual(r.data['gallery'][0]['image'], cover)
        r = self.client.delete(f'{self.url}{photo["id"]}/')
        self.assertEqual(r.data['gallery'], [])

    def test_limit_and_not_image(self):
        r = self.client.post(self.url, {'images': [png_file(f'{i}.png') for i in range(MAX_PHOTOS + 1)]},
                             format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertIn(f'не больше {MAX_PHOTOS}', r.data['detail'])
        bad = SimpleUploadedFile('x.png', b'not image', content_type='image/png')
        self.assertEqual(self.client.post(self.url, {'images': [bad]}, format='multipart').status_code, 400)

    def test_other_seller_cannot_touch(self):
        auth(self.client, make_seller('other@test.ru', 'Чужой'))
        self.assertEqual(self.client.post(self.url, {'images': [png_file()]}, format='multipart').status_code, 404)

    def test_shared_file_not_deleted_while_used_elsewhere(self):
        from .models import ProductImage
        data = self.client.post(self.url, {'images': [png_file('1.png'), png_file('2.png')]}, format='multipart').data
        photo = ProductImage.objects.get(pk=data['gallery'][0]['id'])
        other = make_product(self.shop, name='Другой')
        other.image = photo.image.name  # тот же файл у другого товара
        other.save()
        self.client.delete(f'{self.url}{photo.pk}/')
        self.assertTrue(other.image.storage.exists(other.image.name))

