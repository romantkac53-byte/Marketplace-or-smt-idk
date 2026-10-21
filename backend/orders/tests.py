from rest_framework.test import APITestCase

from delivery.models import Delivery, PickupPoint
from marketplace.testing import auth, make_customer, make_product, make_seller, make_staff
from payments.models import top_up
from users.models import User

from .models import Order, SellerOrder

S = SellerOrder.Status


class OrderApiTests(APITestCase):
    def setUp(self):
        self.shop_a = make_seller('a@test.ru', 'Аптека')
        self.shop_b = make_seller('b@test.ru', 'Овощи')
        self.spray = make_product(self.shop_a, name='Спрей', price=200, stock=10)
        self.tomato = make_product(self.shop_b, name='Томат', price=50, stock=10)
        self.buyer = make_customer()
        self.customer = self.buyer.customer
        auth(self.client, self.buyer)

    def fill_cart(self):
        self.client.post('/api/cart/items/', {'product_id': self.spray.pk, 'quantity': 2})
        self.client.post('/api/cart/items/', {'product_id': self.tomato.pk, 'quantity': 3})

    def place(self, **data):
        self.fill_cart()
        return self.client.post('/api/orders/', {'delivery_type': 'courier', **data}, format='json')

    def ship_and_deliver(self, order_id):
        """Действия персонала — пока через модели (их API — в следующей части)."""
        courier = make_staff(f'courier{order_id}@test.ru', User.Role.COURIER)
        for so in Order.objects.get(pk=order_id).seller_orders.exclude(status=S.CANCELLED):
            for st in (S.CONFIRMED, S.ASSEMBLING, S.READY):
                so.change_status(st)
            d = Delivery.objects.get(seller_order=so)
            d.assign_courier(courier)
            d.pick_up()
            if d.is_pickup:
                d.arrive_at_pickup_point()

    def test_place_order_splits_by_seller_and_clears_cart(self):
        r = self.place()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['total_amount'], '550.00')
        self.assertEqual(sorted(so['seller'] for so in r.data['seller_orders']), ['Аптека', 'Овощи'])
        self.assertEqual(r.data['payment']['status'], 'pending')
        self.assertEqual(r.data['delivery_address'], 'ул. Тестовая, 1')  # из профиля
        self.assertEqual(self.client.get('/api/cart/').data['items'], [])

    def test_empty_cart_and_pickup_without_point(self):
        r = self.client.post('/api/orders/', {'delivery_type': 'courier'}, format='json')
        self.assertEqual((r.status_code, r.data['detail']), (400, 'Корзина пуста'))
        self.fill_cart()
        r = self.client.post('/api/orders/', {'delivery_type': 'pickup'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('pickup_point_id', r.data)

    def test_pickup_order_uses_point_address(self):
        point = PickupPoint.objects.create(name='ПВЗ-1', city='Москва', address='ул. Пушкина, 5')
        r = self.place(delivery_type='pickup', pickup_point_id=point.pk)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['delivery_address'], 'ул. Пушкина, 5')
        self.assertEqual(r.data['pickup_point']['name'], 'ПВЗ-1')

    def test_pay_without_money_then_after_top_up(self):
        order_id = self.place().data['id']
        r = self.client.post(f'/api/orders/{order_id}/pay/')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Недостаточно средств', r.data['detail'])
        self.assertEqual(self.client.get(f'/api/orders/{order_id}/').data['payment']['status'], 'failed')

        top_up(self.customer, 1000)
        r = self.client.post(f'/api/orders/{order_id}/pay/')
        self.assertEqual((r.data['status'], r.data['payment']['status']), ('paid', 'paid'))
        self.assertEqual(self.client.get('/api/balance/').data['balance'], '450.00')
        types = [t['type'] for t in self.client.get('/api/balance/transactions/').data['results']]
        self.assertEqual(types, ['payment', 'topup'])

    def test_cancel_paid_order_refunds_everything(self):
        top_up(self.customer, 1000)
        order_id = self.place().data['id']
        self.client.post(f'/api/orders/{order_id}/pay/')
        r = self.client.post(f'/api/orders/{order_id}/cancel/', {'comment': 'передумал'})
        self.assertEqual(r.data['status'], 'cancelled')
        self.assertEqual(r.data['payment']['status'], 'refunded')
        self.assertEqual(self.client.get('/api/balance/').data['balance'], '1000.00')

    def test_cancel_one_seller_order(self):
        top_up(self.customer, 1000)
        data = self.place().data
        self.client.post(f'/api/orders/{data["id"]}/pay/')
        veg = next(so for so in data['seller_orders'] if so['seller'] == 'Овощи')
        r = self.client.post(f'/api/orders/{data["id"]}/seller-orders/{veg["id"]}/cancel/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['status'], 'paid')  # другая часть заказа продолжает выполняться
        self.assertEqual(r.data['payment']['status'], 'partially_refunded')
        self.assertEqual(self.client.get('/api/balance/').data['balance'], '600.00')

    def test_tracking_shows_code_and_blocks_cancel_in_transit(self):
        top_up(self.customer, 1000)
        order_id = self.place().data['id']
        self.client.post(f'/api/orders/{order_id}/pay/')
        self.ship_and_deliver(order_id)
        data = self.client.get(f'/api/orders/{order_id}/').data
        delivery = data['seller_orders'][0]['delivery']
        self.assertEqual(delivery['status'], 'in_transit')
        self.assertEqual(len(delivery['pickup_code']), 6)
        self.assertEqual([h['status'] for h in delivery['history']], ['pending', 'assigned', 'in_transit'])
        self.assertFalse(data['seller_orders'][0]['can_cancel'])
        r = self.client.post(f'/api/orders/{order_id}/cancel/')
        self.assertEqual(r.status_code, 400)

    def test_customer_sees_only_own_orders(self):
        order_id = self.place().data['id']
        other = make_customer('other@test.ru')
        auth(self.client, other)
        self.assertEqual(self.client.get('/api/orders/').data['count'], 0)
        self.assertEqual(self.client.get(f'/api/orders/{order_id}/').status_code, 404)
        self.assertEqual(self.client.post(f'/api/orders/{order_id}/pay/').status_code, 404)

    def test_seller_has_no_customer_orders_api(self):
        auth(self.client, self.shop_a)
        self.assertEqual(self.client.get('/api/orders/').status_code, 403)


class PickupPointApiTests(APITestCase):
    def test_public_list_only_active(self):
        PickupPoint.objects.create(name='Открыт', city='Москва', address='a')
        PickupPoint.objects.create(name='Закрыт', city='Москва', address='b', is_active=False)
        PickupPoint.objects.create(name='Другой город', city='Казань', address='c')
        r = self.client.get('/api/pickup-points/', {'city': 'Москва'})
        self.assertEqual([p['name'] for p in r.data], ['Открыт'])
