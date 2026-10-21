from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from marketplace.testing import auth, make_customer, make_paid_order, make_product, make_seller, make_staff
from orders.models import SellerOrder
from users.models import User

from .models import Delivery, PickupPoint

S = SellerOrder.Status


def ready_delivery(buyer, product, pickup_point=None):
    """Оплаченный и собранный заказ — посылка ждёт курьера."""
    customer = buyer.customer
    customer.add_to_cart(product, 1)
    order = customer.place_order(pickup_point=pickup_point)
    from payments.models import top_up
    top_up(customer, order.total_amount)
    order.pay()
    seller_order = order.seller_orders.get()
    for status in (S.CONFIRMED, S.ASSEMBLING, S.READY):
        seller_order.change_status(status)
    return Delivery.objects.get(seller_order=seller_order)


class CourierApiTests(APITestCase):
    def setUp(self):
        self.product = make_product(make_seller(), price=100, stock=10)
        self.buyer = make_customer()
        self.buyer.customer.phone = '+79990001122'
        self.buyer.customer.save()
        self.courier = make_staff('courier@test.ru', User.Role.COURIER)
        auth(self.client, self.courier)

    def test_take_pick_up_hand_over_with_code(self):
        delivery = ready_delivery(self.buyer, self.product)
        available = self.client.get('/api/courier/deliveries/available/').data['results']
        self.assertEqual(available[0]['recipient']['phone'], '+79990001122')
        self.assertNotIn('pickup_code', available[0])  # код курьеру не показывается

        self.client.post(f'/api/courier/deliveries/{delivery.pk}/take/')
        self.client.post(f'/api/courier/deliveries/{delivery.pk}/pick-up/')
        r = self.client.post(f'/api/courier/deliveries/{delivery.pk}/hand-over/', {'code': '000000'
                             if delivery.pickup_code != '000000' else '111111'})
        self.assertEqual(r.status_code, 400)
        r = self.client.post(f'/api/courier/deliveries/{delivery.pk}/hand-over/', {'code': delivery.pickup_code})
        self.assertEqual(r.data['status'], 'delivered')

    def test_cannot_take_taken_or_act_on_foreign(self):
        delivery = ready_delivery(self.buyer, self.product)
        self.client.post(f'/api/courier/deliveries/{delivery.pk}/take/')
        auth(self.client, make_staff('courier2@test.ru', User.Role.COURIER))
        self.assertEqual(self.client.post(f'/api/courier/deliveries/{delivery.pk}/take/').status_code, 404)
        self.assertEqual(self.client.post(f'/api/courier/deliveries/{delivery.pk}/pick-up/').status_code, 404)

    def test_fail_returns_goods_and_money(self):
        delivery = ready_delivery(self.buyer, self.product)
        self.client.post(f'/api/courier/deliveries/{delivery.pk}/take/')
        self.client.post(f'/api/courier/deliveries/{delivery.pk}/pick-up/')
        r = self.client.post(f'/api/courier/deliveries/{delivery.pk}/fail/', {'comment': 'Не открыли дверь'})
        self.assertEqual(r.data['status'], 'returned')
        self.buyer.customer.refresh_from_db()
        self.assertEqual(self.buyer.customer.balance, 100)


class PickupPointApiTests(APITestCase):
    def setUp(self):
        self.product = make_product(make_seller(), price=100, stock=10)
        self.buyer = make_customer()
        self.point = PickupPoint.objects.create(name='ПВЗ-1', city='Москва', address='a', storage_days=3)
        self.other_point = PickupPoint.objects.create(name='ПВЗ-2', city='Москва', address='b')
        self.employee = make_staff('pvz@test.ru', User.Role.PICKUP)
        self.point.employees.add(self.employee)
        self.courier = make_staff('courier@test.ru', User.Role.COURIER)

    def in_transit(self, point):
        delivery = ready_delivery(self.buyer, self.product, pickup_point=point)
        delivery.assign_courier(self.courier)
        delivery.pick_up()
        return delivery

    def test_accept_find_by_code_issue(self):
        delivery = self.in_transit(self.point)
        auth(self.client, self.employee)
        self.assertEqual(self.client.get('/api/pickup/deliveries/').data['count'], 1)  # едет к нам
        r = self.client.post(f'/api/pickup/deliveries/{delivery.pk}/accept/')
        self.assertEqual(r.data['status'], 'at_pickup_point')
        found = self.client.get('/api/pickup/deliveries/', {'code': delivery.pickup_code}).data['results']
        self.assertEqual([d['id'] for d in found], [delivery.pk])
        r = self.client.post(f'/api/pickup/deliveries/{delivery.pk}/issue/', {'code': delivery.pickup_code})
        self.assertEqual(r.data['status'], 'delivered')

    def test_other_point_parcels_invisible(self):
        delivery = self.in_transit(self.other_point)
        auth(self.client, self.employee)
        self.assertEqual(self.client.get('/api/pickup/deliveries/').data['count'], 0)
        self.assertEqual(self.client.post(f'/api/pickup/deliveries/{delivery.pk}/accept/').status_code, 404)

    def test_return_expired_only_own_point(self):
        mine = self.in_transit(self.point)
        foreign = self.in_transit(self.other_point)
        for delivery in (mine, foreign):
            delivery.arrive_at_pickup_point()
        Delivery.objects.update(storage_until=timezone.now() - timedelta(days=1))
        auth(self.client, self.employee)
        self.assertEqual(self.client.post('/api/pickup/deliveries/return-expired/').data['returned'], 1)
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, Delivery.Status.AT_PICKUP_POINT)


class ManagerDeliveryApiTests(APITestCase):
    def test_assign_courier(self):
        delivery = ready_delivery(make_customer(), make_product(make_seller(), stock=5))
        courier = make_staff('courier@test.ru', User.Role.COURIER)
        auth(self.client, make_staff('manager@test.ru', User.Role.MANAGER))
        self.assertEqual(self.client.get('/api/manager/deliveries/couriers/').data[0]['id'], courier.pk)
        r = self.client.post(f'/api/manager/deliveries/{delivery.pk}/assign/', {'courier_id': courier.pk})
        self.assertEqual(r.data['status'], 'assigned')
        not_courier = make_staff('stock@test.ru', User.Role.WAREHOUSE)
        r = self.client.post(f'/api/manager/deliveries/{delivery.pk}/assign/', {'courier_id': not_courier.pk})
        self.assertEqual(r.status_code, 400)
