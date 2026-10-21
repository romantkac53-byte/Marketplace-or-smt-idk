"""Сквозной тест: полный цикл продажи из ТЗ — только через API, как это делает фронтенд.

размещение товара → поиск → заказ → оплата → сборка → доставка → получение → отзыв → возврат
"""
from rest_framework.test import APIClient, APITestCase

from catalog.models import Category
from delivery.models import PickupPoint
from payments.models import top_up
from users.models import Customer, User

from .testing import PASSWORD, make_staff


class FullSaleCycleTest(APITestCase):
    def client_for(self, user=None, email=None):
        client = APIClient()
        email = email or user.email
        token = client.post('/api/auth/login/', {'email': email, 'password': PASSWORD}).data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return client

    def test_full_cycle(self):
        spray_category = Category.objects.create(name='Лекарства', slug='meds').add_subcategory('Спреи', 'spray')
        point = PickupPoint.objects.create(name='ПВЗ на Ленина', city='Москва', address='ул. Ленина, 1')
        manager = self.client_for(make_staff('manager@test.ru', User.Role.MANAGER))
        warehouse = self.client_for(make_staff('stock@test.ru', User.Role.WAREHOUSE))
        courier = self.client_for(make_staff('courier@test.ru', User.Role.COURIER))
        pvz_user = make_staff('pvz@test.ru', User.Role.PICKUP)
        point.employees.add(pvz_user)
        pvz = self.client_for(pvz_user)

        # 1. Продавец регистрируется, менеджер одобряет магазин
        r = self.client.post('/api/auth/register/seller/',
                             {'email': 'shop@test.ru', 'password': PASSWORD, 'store_name': 'Аптека', 'accept_terms': True})
        seller_id = r.data['user']['id']
        seller = self.client_for(email='shop@test.ru')
        shop_id = manager.get('/api/manager/sellers/', {'status': 'pending'}).data['results'][0]['id']
        self.assertEqual(manager.post(f'/api/manager/sellers/{shop_id}/set-status/', {'status': 'active'})
                         .data['status'], 'active')

        # 2. Продавец размещает товар, склад принимает поставку
        product_id = seller.post('/api/seller/products/', {
            'name': 'Спрей для носа', 'category_id': spray_category.pk, 'price': '300.00'}, format='json').data['id']
        r = warehouse.post('/api/warehouse/movements/', {'product_id': product_id, 'type': 'receipt', 'quantity': 10})
        self.assertEqual(r.data['stock_after'], 10)

        # 3. Покупатель регистрируется, находит товар поиском, кладёт в корзину, оформляет в ПВЗ
        self.client.post('/api/auth/register/customer/', {'email': 'buyer@test.ru', 'password': PASSWORD, 'accept_terms': True})
        buyer = self.client_for(email='buyer@test.ru')
        found = buyer.get('/api/products/', {'search': 'спрей'}).data['results']
        self.assertEqual([p['id'] for p in found], [product_id])
        buyer.post('/api/cart/items/', {'product_id': product_id, 'quantity': 2})
        order = buyer.post('/api/orders/', {'delivery_type': 'pickup', 'pickup_point_id': point.pk},
                           format='json').data
        self.assertEqual(order['total_amount'], '600.00')

        # 4. Оплата (баланс пополняет администратор — имитация)
        top_up(Customer.objects.get(user__email='buyer@test.ru'), 1000)
        self.assertEqual(buyer.post(f'/api/orders/{order["id"]}/pay/').data['status'], 'paid')

        # 5. Продавец подтверждает, склад собирает
        seller_order_id = seller.get('/api/seller/orders/').data['results'][0]['id']
        seller.post(f'/api/seller/orders/{seller_order_id}/confirm/')
        warehouse.post(f'/api/warehouse/assembly/{seller_order_id}/start/')
        self.assertEqual(warehouse.post(f'/api/warehouse/assembly/{seller_order_id}/ready/').data['status'], 'ready')

        # 6. Курьер берёт посылку и везёт в ПВЗ; ПВЗ принимает
        delivery_id = courier.get('/api/courier/deliveries/available/').data['results'][0]['id']
        courier.post(f'/api/courier/deliveries/{delivery_id}/take/')
        courier.post(f'/api/courier/deliveries/{delivery_id}/pick-up/')
        self.assertEqual(pvz.post(f'/api/pickup/deliveries/{delivery_id}/accept/').data['status'], 'at_pickup_point')

        # 7. Покупатель видит код в заказе, называет его в ПВЗ — посылка выдана
        code = buyer.get(f'/api/orders/{order["id"]}/').data['seller_orders'][0]['delivery']['pickup_code']
        self.assertEqual(len(pvz.get('/api/pickup/deliveries/', {'code': code}).data['results']), 1)
        self.assertEqual(pvz.post(f'/api/pickup/deliveries/{delivery_id}/issue/', {'code': code}).data['status'],
                         'delivered')
        self.assertEqual(buyer.get(f'/api/orders/{order["id"]}/').data['status'], 'completed')

        # 8. Отзыв — и продавец отвечает
        review_id = buyer.post('/api/reviews/', {'product_id': product_id, 'rating': 5, 'text': 'Помог!'}).data['id']
        seller.post(f'/api/seller/reviews/{review_id}/reply/', {'text': 'Будьте здоровы!'})
        self.assertEqual(buyer.get(f'/api/products/{product_id}/').data['rating'], 5.0)

        # 9. Возврат одной штуки: заявка → менеджер одобряет → склад принимает → деньги на баланс
        item_id = buyer.get(f'/api/orders/{order["id"]}/').data['seller_orders'][0]['items'][0]['id']
        return_id = buyer.post('/api/returns/', {'order_item_id': item_id, 'quantity': 1, 'reason': 'not_fit'}).data['id']
        manager.post(f'/api/manager/returns/{return_id}/approve/')
        r = warehouse.post(f'/api/warehouse/returns/{return_id}/accept/')
        self.assertEqual((r.data['status'], r.data['refund_amount']), ('completed', '300.00'))
        self.assertEqual(buyer.get('/api/balance/').data['balance'], '700.00')  # 1000 − 600 + 300

        # Итог по складу: было 10, продано 2, вернули 1
        stock = warehouse.get('/api/warehouse/stock/').data['results'][0]
        self.assertEqual((stock['stock'], stock['reserved']), (9, 0))
        self.assertTrue(seller_id)
