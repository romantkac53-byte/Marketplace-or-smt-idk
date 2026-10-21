from rest_framework.test import APITestCase

from marketplace.testing import auth, make_customer, make_delivered_order, make_paid_order, make_product, make_seller


class ReturnApiTests(APITestCase):
    def setUp(self):
        self.seller = make_seller()
        self.product = make_product(self.seller, price=100, stock=10)
        self.buyer = make_customer()
        auth(self.client, self.buyer)
        self.order = make_delivered_order(self.buyer, (self.product, 3))
        self.item = self.order.seller_orders.get().items.get()

    def returnable(self):
        data = self.client.get(f'/api/orders/{self.order.pk}/').data
        return data['seller_orders'][0]['items'][0]['returnable_quantity']

    def test_create_and_cancel(self):
        self.assertEqual(self.returnable(), 3)
        r = self.client.post('/api/returns/', {'order_item_id': self.item.pk, 'quantity': 2, 'reason': 'defect'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['status'], r.data['amount']), ('requested', '200.00'))
        self.assertEqual(self.returnable(), 1)

        r = self.client.post('/api/returns/', {'order_item_id': self.item.pk, 'quantity': 2, 'reason': 'other'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('от 1 до 1', r.data['detail'])

        return_id = self.client.get('/api/returns/').data['results'][0]['id']
        r = self.client.post(f'/api/returns/{return_id}/cancel/')
        self.assertEqual(r.data['status'], 'cancelled')
        self.assertEqual(self.returnable(), 3)

    def test_not_delivered_item(self):
        order = make_paid_order(self.buyer, (self.product, 1))
        item = order.seller_orders.get().items.get()
        r = self.client.post('/api/returns/', {'order_item_id': item.pk, 'quantity': 1, 'reason': 'other'})
        self.assertEqual(r.status_code, 400)

    def test_foreign_item_invisible(self):
        auth(self.client, make_customer('other@test.ru'))
        r = self.client.post('/api/returns/', {'order_item_id': self.item.pk, 'quantity': 1, 'reason': 'other'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('order_item_id', r.data)  # «нет такой позиции» — о чужом заказе ничего не сообщаем

    def test_seller_sees_returns_of_own_products(self):
        self.client.post('/api/returns/', {'order_item_id': self.item.pk, 'quantity': 1, 'reason': 'not_fit'})
        auth(self.client, self.seller)
        self.assertEqual(self.client.get('/api/seller/returns/').data['count'], 1)
        auth(self.client, make_seller('other@test.ru', 'Чужой'))
        self.assertEqual(self.client.get('/api/seller/returns/').data['count'], 0)


class ManagerReturnApiTests(APITestCase):
    def test_reject_requires_reason_and_approve_goes_to_warehouse(self):
        from marketplace.testing import make_staff
        from users.models import User
        product = make_product(make_seller(), price=100, stock=10)
        buyer = make_customer()
        item = make_delivered_order(buyer, (product, 2)).seller_orders.get().items.get()
        first = buyer.customer.request_return(item, 1, 'not_fit')
        second = buyer.customer.request_return(item, 1, 'defect')
        auth(self.client, make_staff('manager@test.ru', User.Role.MANAGER))
        self.assertEqual(self.client.post(f'/api/manager/returns/{first.pk}/reject/').status_code, 400)
        r = self.client.post(f'/api/manager/returns/{first.pk}/reject/', {'comment': 'Следы использования'})
        self.assertEqual((r.data['status'], r.data['manager_comment']), ('rejected', 'Следы использования'))
        self.client.post(f'/api/manager/returns/{second.pk}/approve/')
        auth(self.client, make_staff('stock@test.ru', User.Role.WAREHOUSE))
        self.assertEqual([x['id'] for x in self.client.get('/api/warehouse/returns/').data['results']], [second.pk])
