from rest_framework.test import APITestCase

from marketplace.testing import auth, make_customer, make_product, make_seller, make_staff
from users.models import User


class CartApiTests(APITestCase):
    def setUp(self):
        self.shop = make_seller()
        self.product = make_product(self.shop, price=150, stock=5)
        self.buyer = make_customer()
        auth(self.client, self.buyer)

    def test_add_increments_and_totals(self):
        self.client.post('/api/cart/items/', {'product_id': self.product.pk, 'quantity': 2})
        r = self.client.post('/api/cart/items/', {'product_id': self.product.pk})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.data['items']), 1)
        self.assertEqual(r.data['items_count'], 3)
        self.assertEqual(r.data['total_price'], '450.00')

    def test_cannot_exceed_available(self):
        r = self.client.post('/api/cart/items/', {'product_id': self.product.pk, 'quantity': 6})
        self.assertEqual(r.status_code, 400)
        self.assertIn('Доступно только 5', r.data['detail'])

    def test_set_quantity_and_remove(self):
        item_id = self.client.post('/api/cart/items/', {'product_id': self.product.pk}).data['items'][0]['id']
        r = self.client.patch(f'/api/cart/items/{item_id}/', {'quantity': 4})
        self.assertEqual(r.data['items'][0]['quantity'], 4)
        self.assertEqual(self.client.patch(f'/api/cart/items/{item_id}/', {'quantity': 0}).status_code, 400)
        r = self.client.delete(f'/api/cart/items/{item_id}/')
        self.assertEqual(r.data['items'], [])

    def test_cannot_touch_someone_elses_cart_item(self):
        other = make_customer('other@test.ru')
        other.customer.add_to_cart(self.product, 1)
        foreign_id = other.customer.cart.items.first().pk
        self.assertEqual(self.client.delete(f'/api/cart/items/{foreign_id}/').status_code, 404)

    def test_only_customers_have_cart(self):
        self.client.credentials()
        self.assertEqual(self.client.get('/api/cart/').status_code, 401)
        auth(self.client, make_staff('courier@test.ru', User.Role.COURIER))
        self.assertEqual(self.client.get('/api/cart/').status_code, 403)
