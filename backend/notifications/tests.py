"""Уведомления создаются по событиям заказа, доставки, возврата, отзыва."""
from rest_framework.test import APITestCase

from delivery.models import Delivery, PickupPoint
from marketplace.testing import (auth, make_customer, make_delivered_order, make_paid_order, make_product, make_seller,
                                 make_staff)
from payments.models import top_up
from users.models import User

from .models import Notification


def texts(user):
    return list(Notification.objects.filter(user=user).order_by('id').values_list('text', flat=True))


def has(user, fragment):
    return any(fragment in text for text in texts(user))


class NotificationEventsTests(APITestCase):
    def setUp(self):
        self.shop = make_seller()
        self.product = make_product(self.shop, name='Спрей', price=100, stock=10)
        self.buyer = make_customer()

    def test_paid_order_notifies_buyer_and_seller(self):
        order = make_paid_order(self.buyer, (self.product, 2))
        self.assertIn(f'Заказ №{order.pk} оплачен — магазины начали сборку', texts(self.buyer))
        self.assertTrue(has(self.shop, 'Новый заказ'))

    def test_delivery_journey(self):
        order = make_delivered_order(self.buyer, (self.product, 1))
        self.assertTrue(has(self.buyer, 'в пути'))
        self.assertTrue(has(self.buyer, 'получена'))
        self.assertTrue(has(self.buyer, f'Заказ №{order.pk} выполнен'))

    def test_pickup_point_and_courier_assignment(self):
        point = PickupPoint.objects.create(name='ПВЗ-1', city='Москва', address='a')
        self.buyer.customer.add_to_cart(self.product, 1)
        order = self.buyer.customer.place_order(pickup_point=point)
        top_up(self.buyer.customer, 1000)
        order.pay()
        seller_order = order.seller_orders.get()
        for status in ('confirmed', 'assembling', 'ready'):
            seller_order.change_status(status)
        courier = make_staff('courier@test.ru', User.Role.COURIER)
        manager = make_staff('manager@test.ru', User.Role.MANAGER)
        delivery = Delivery.objects.get(seller_order=seller_order)
        delivery.assign_courier(courier, changed_by=manager)
        self.assertTrue(has(courier, 'Вам назначена посылка'))
        delivery.pick_up(changed_by=courier)
        delivery.arrive_at_pickup_point()
        self.assertTrue(has(self.buyer, 'ждёт вас в пункте «ПВЗ-1»'))

    def test_courier_taking_parcel_himself_gets_no_notification(self):
        order = make_paid_order(self.buyer, (self.product, 1))
        seller_order = order.seller_orders.get()
        for status in ('confirmed', 'assembling', 'ready'):
            seller_order.change_status(status)
        courier = make_staff('courier@test.ru', User.Role.COURIER)
        Delivery.objects.get(seller_order=seller_order).assign_courier(courier, changed_by=courier)
        self.assertEqual(texts(courier), [])

    def test_seller_cancel_notifies_buyer_with_reason(self):
        order = make_paid_order(self.buyer, (self.product, 1))
        order.seller_orders.get().cancel(changed_by=self.shop, comment='Нет в наличии')
        self.assertTrue(any('отменил свою часть' in t and 'Нет в наличии' in t for t in texts(self.buyer)))

    def test_review_and_return(self):
        order = make_delivered_order(self.buyer, (self.product, 2))
        self.buyer.customer.leave_review(self.product, 5, 'Отлично')
        self.assertTrue(has(self.shop, 'Новый отзыв'))
        ret = self.buyer.customer.request_return(order.seller_orders.get().items.get(), 1, 'defect')
        self.assertTrue(has(self.shop, 'оформил возврат'))
        ret.manager_comment = 'Следы использования'
        ret.reject()
        self.assertTrue(has(self.buyer, 'отклонён: Следы использования'))


class NotificationApiTests(APITestCase):
    def test_list_unread_read_all_and_isolation(self):
        buyer = make_customer()
        other = make_customer('other@test.ru')
        for i in range(3):
            Notification.objects.create(user=buyer, text=f'n{i}')
        Notification.objects.create(user=other, text='чужое')
        auth(self.client, buyer)
        self.assertEqual(self.client.get('/api/notifications/unread-count/').data['unread'], 3)
        first = self.client.get('/api/notifications/').data['results'][0]
        self.assertEqual(first['text'], 'n2')  # новые сверху
        self.client.post(f'/api/notifications/{first["id"]}/read/')
        self.assertEqual(self.client.get('/api/notifications/unread-count/').data['unread'], 2)
        self.assertEqual(self.client.post('/api/notifications/read-all/').data['updated'], 2)
        foreign = Notification.objects.get(user=other).pk
        self.assertEqual(self.client.post(f'/api/notifications/{foreign}/read/').status_code, 404)

    def test_manager_approval_notifies_seller(self):
        seller = make_seller('new@test.ru', 'Новый', status='pending')
        auth(self.client, make_staff('manager@test.ru', User.Role.MANAGER))
        self.client.post(f'/api/manager/sellers/{seller.seller.pk}/set-status/', {'status': 'active'})
        self.assertIn('Ваш магазин одобрен — товары появились в каталоге', texts(seller))
