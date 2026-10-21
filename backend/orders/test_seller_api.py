from rest_framework.test import APITestCase

from marketplace.testing import auth, make_customer, make_paid_order, make_product, make_seller


class SellerOrderApiTests(APITestCase):
    def setUp(self):
        self.shop = make_seller('a@test.ru', 'Аптека')
        self.other_shop = make_seller('b@test.ru', 'Овощи')
        self.spray = make_product(self.shop, name='Спрей', price=200, stock=10)
        self.tomato = make_product(self.other_shop, name='Томат', price=50, stock=10)
        self.buyer = make_customer()
        auth(self.client, self.shop)

    def test_sees_only_paid_orders_of_own_shop(self):
        self.buyer.customer.add_to_cart(self.spray, 1)
        self.buyer.customer.place_order()  # не оплачен — продавцу не виден
        make_paid_order(self.buyer, (self.spray, 2), (self.tomato, 1))
        r = self.client.get('/api/seller/orders/')
        self.assertEqual(r.data['count'], 1)
        order = r.data['results'][0]
        self.assertEqual([i['product_name'] for i in order['items']], ['Спрей'])  # без чужих товаров
        self.assertEqual((order['subtotal'], order['commission'], order['seller_payout']),
                         ('400.00', '40.00', '360.00'))
        self.assertNotIn('delivery_address', order)  # данные покупателя продавцу не нужны

    def test_confirm(self):
        seller_order_id = make_paid_order(self.buyer, (self.spray, 1)).seller_orders.get().pk
        r = self.client.post(f'/api/seller/orders/{seller_order_id}/confirm/')
        self.assertEqual(r.data['status'], 'confirmed')
        r = self.client.post(f'/api/seller/orders/{seller_order_id}/confirm/')
        self.assertEqual(r.status_code, 400)  # повторно — недопустимый переход

    def test_cancel_requires_reason_and_refunds_buyer(self):
        order = make_paid_order(self.buyer, (self.spray, 2))
        seller_order_id = order.seller_orders.get().pk
        self.assertEqual(self.client.post(f'/api/seller/orders/{seller_order_id}/cancel/').status_code, 400)
        r = self.client.post(f'/api/seller/orders/{seller_order_id}/cancel/', {'comment': 'Нет в наличии'})
        self.assertEqual(r.data['status'], 'cancelled')
        self.buyer.customer.refresh_from_db()
        self.assertEqual(self.buyer.customer.balance, 400)
        self.assertIn('Нет в наличии', r.data['history'][-1]['comment'])

    def test_cannot_touch_other_shop_order(self):
        seller_order_id = make_paid_order(self.buyer, (self.tomato, 1)).seller_orders.get().pk
        self.assertEqual(self.client.post(f'/api/seller/orders/{seller_order_id}/confirm/').status_code, 404)
