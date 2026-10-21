from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from marketplace.testing import auth, make_product, make_seller


class SellerPromotionApiTests(APITestCase):
    def setUp(self):
        self.seller = make_seller()
        self.mine = make_product(self.seller, name='Мой', price=100)
        self.foreign = make_product(make_seller('other@test.ru', 'Чужой'), name='Чужой', price=100)
        auth(self.client, self.seller)
        now = timezone.now()
        self.period = {'starts_at': (now - timedelta(days=1)).isoformat(),
                       'ends_at': (now + timedelta(days=7)).isoformat()}

    def post(self, **data):
        return self.client.post('/api/seller/promotions/',
                                {'name': 'Скидка', 'discount_type': 'percent', 'value': '20', **self.period, **data},
                                format='json')

    def test_shop_wide_promotion_affects_only_own_products(self):
        r = self.post()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['is_running'])
        prices = {p['name']: p['current_price'] for p in self.client.get('/api/products/').data['results']}
        self.assertEqual(prices, {'Мой': '80.00', 'Чужой': '100.00'})

    def test_foreign_products_rejected(self):
        r = self.post(product_ids=[self.foreign.pk])
        self.assertEqual(r.status_code, 400)
        self.assertIn('product_ids', r.data)

    def test_model_validation(self):
        r = self.post(value='150', ends_at=(timezone.now() - timedelta(days=5)).isoformat())
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.data), {'value', 'ends_at'})

    def test_other_seller_promotions_hidden(self):
        promo_id = self.post().data['id']
        auth(self.client, make_seller('third@test.ru', 'Третий'))
        self.assertEqual(self.client.get('/api/seller/promotions/').data['count'], 0)
        self.assertEqual(self.client.delete(f'/api/seller/promotions/{promo_id}/').status_code, 404)


class ManagerPromotionApiTests(APITestCase):
    def test_platform_wide_promotion(self):
        from marketplace.testing import make_staff
        from users.models import User
        make_product(make_seller('a@test.ru', 'A'), name='A', price=100)
        make_product(make_seller('b@test.ru', 'B'), name='B', price=200)
        auth(self.client, make_staff('manager@test.ru', User.Role.MANAGER))
        now = timezone.now()
        r = self.client.post('/api/manager/promotions/', {
            'name': 'Чёрная пятница', 'discount_type': 'percent', 'value': '10',
            'starts_at': (now - timedelta(days=1)).isoformat(), 'ends_at': (now + timedelta(days=1)).isoformat(),
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['seller_id'])
        prices = sorted(p['current_price'] for p in self.client.get('/api/products/').data['results'])
        self.assertEqual(prices, ['180.00', '90.00'])


class PromotionStartDefaultTests(APITestCase):
    def test_empty_start_means_now(self):
        seller = make_seller('shop@test.ru', 'Магазин')
        make_product(seller, name='Товар', price=100)
        auth(self.client, seller)
        r = self.client.post('/api/seller/promotions/', {
            'name': 'Сразу', 'discount_type': 'fixed', 'value': '10',
            'ends_at': (timezone.now() + timedelta(days=1)).isoformat(),
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['is_running'])
