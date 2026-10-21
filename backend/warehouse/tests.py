from rest_framework.test import APITestCase

from marketplace.testing import auth, make_customer, make_paid_order, make_product, make_seller, make_staff
from orders.models import SellerOrder
from users.models import User


class WarehouseApiTests(APITestCase):
    def setUp(self):
        self.seller = make_seller()
        self.product = make_product(self.seller, price=100, stock=10)
        auth(self.client, make_staff('stock@test.ru', User.Role.WAREHOUSE))

    def test_only_warehouse_staff(self):
        auth(self.client, make_staff('courier@test.ru', User.Role.COURIER))
        self.assertEqual(self.client.get('/api/warehouse/stock/').status_code, 403)
        auth(self.client, self.seller)
        self.assertEqual(self.client.get('/api/warehouse/stock/').status_code, 403)

    def test_assembly_queue_and_flow(self):
        order = make_paid_order(make_customer(), (self.product, 2))
        seller_order = order.seller_orders.get()
        self.assertEqual(self.client.get('/api/warehouse/assembly/').data['count'], 0)  # ещё не подтверждён
        seller_order.confirm()
        queue = self.client.get('/api/warehouse/assembly/').data['results']
        self.assertEqual(queue[0]['items'][0]['quantity'], 2)
        self.assertNotIn('price', queue[0]['items'][0])  # сборщику цены не нужны
        self.client.post(f'/api/warehouse/assembly/{seller_order.pk}/start/')
        r = self.client.post(f'/api/warehouse/assembly/{seller_order.pk}/ready/')
        self.assertEqual(r.data['status'], SellerOrder.Status.READY)
        self.assertTrue(hasattr(SellerOrder.objects.get(pk=seller_order.pk), 'delivery'))

    def test_stock_operations(self):
        make_paid_order(make_customer(), (self.product, 4))  # 4 в резерве
        r = self.client.post('/api/warehouse/movements/',
                             {'product_id': self.product.pk, 'type': 'write_off', 'quantity': 7})
        self.assertEqual(r.status_code, 400)  # нельзя списать зарезервированное
        r = self.client.post('/api/warehouse/movements/',
                             {'product_id': self.product.pk, 'type': 'inventory', 'quantity': 12, 'comment': 'пересчёт'})
        self.assertEqual((r.status_code, r.data['stock_delta']), (201, 2))
        r = self.client.post('/api/warehouse/movements/', {'product_id': self.product.pk, 'type': 'reserve',
                                                           'quantity': 1})
        self.assertEqual(r.status_code, 400)  # системные операции вручную недоступны
        low = self.client.get('/api/warehouse/stock/', {'low': 9}).data['results']
        self.assertEqual(low[0]['available'], 8)
        self.assertEqual(self.client.get('/api/warehouse/stock/', {'low': 8}).data['count'], 0)
