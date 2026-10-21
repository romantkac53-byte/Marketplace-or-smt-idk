"""Отчёты: числа посчитаны вручную, тест сверяет с ними формулы.

Данные:
  Аптека: Спрей 100 ₽ (Лекарства → Спреи, комиссия 15% от родителя). Овощи: Томат 50 ₽ (Еда, 10% — общий процент).
  Заказ A (оплачен, доставлен): Спрей × 2 + Томат × 3  → 200 + 150 = 350 ₽; комиссия 30 + 15 = 45 ₽
  Заказ B (оплачен, продавец отменил): Спрей × 1        → в продажи не входит, но это 1 отменённый подзаказ из 3
  Заказ C (не оплачен): Томат × 1                        → никуда не входит
  Возврат по заказу A: Томат × 1, принят складом        → 50 ₽
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from catalog.models import Category
from marketplace.testing import auth, make_customer, make_delivered_order, make_paid_order, make_product, make_seller, make_staff
from users.models import User


class ReportsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        meds = Category.objects.create(name='Лекарства', slug='meds', commission_percent=15)
        spray_cat = meds.add_subcategory('Спреи', 'spray')
        food = Category.objects.create(name='Еда', slug='food')
        cls.pharmacy = make_seller('a@test.ru', 'Аптека')
        cls.veg = make_seller('b@test.ru', 'Овощи')
        cls.spray = make_product(cls.pharmacy, spray_cat, 'Спрей', price=100, stock=20)
        cls.tomato = make_product(cls.veg, food, 'Томат', price=50, stock=20)
        buyer = make_customer()

        order_a = make_delivered_order(buyer, (cls.spray, 2), (cls.tomato, 3))
        order_b = make_paid_order(buyer, (cls.spray, 1))
        order_b.seller_orders.get().cancel(comment='нет товара')
        buyer.customer.add_to_cart(cls.tomato, 1)
        buyer.customer.place_order()  # заказ C — не оплачен
        item = order_a.seller_orders.get(seller=cls.veg.seller).items.get()
        ret = buyer.customer.request_return(item, 1, 'not_fit')
        ret.approve()
        ret.complete()

    def setUp(self):
        auth(self.client, make_staff('boss@test.ru', User.Role.DIRECTOR))

    def test_summary_numbers(self):
        s = self.client.get('/api/reports/dashboard/').data['summary']
        self.assertEqual(float(s['gmv']), 350)
        self.assertEqual(float(s['commission']), 45)
        self.assertEqual(float(s['seller_payout']), 305)
        self.assertEqual(s['orders'], 1)  # B оплачен, но целиком отменён продавцом — это не продажа
        self.assertEqual(s['items_sold'], 5)
        self.assertEqual(float(s['average_check']), 350)  # 350 / 1
        self.assertEqual((float(s['returns_amount']), s['returns_quantity']), (50, 1))
        self.assertEqual(s['returns_share'], 14.3)  # 50 / 350
        self.assertEqual(s['cancelled_share'], 33.3)  # 1 из 3 подзаказов
        self.assertEqual(s['new_customers'], 1)

    def test_previous_period_and_series(self):
        data = self.client.get('/api/reports/dashboard/').data
        self.assertEqual(float(data['previous']['gmv']), 0)
        self.assertEqual(len(data['series']), 30)  # все дни периода, включая дни без продаж
        today = data['series'][-1]
        self.assertEqual((float(today['gmv']), today['orders']), (350, 1))  # B отменён — в продажах нет

    def test_groupings(self):
        today = timezone.localdate()
        weeks = self.client.get('/api/reports/dashboard/', {'group': 'week', 'date_from': today - timedelta(days=20)}).data
        self.assertEqual(sum(float(p['gmv']) for p in weeks['series']), 350)
        months = self.client.get('/api/reports/dashboard/', {'group': 'month'}).data
        self.assertIn(today.replace(day=1).isoformat(), [p['date'] for p in months['series']])

    def test_period_filter_excludes_other_dates(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        r = self.client.get('/api/reports/dashboard/', {'date_from': yesterday - timedelta(days=5), 'date_to': yesterday})
        self.assertEqual(float(r.data['summary']['gmv']), 0)

    def test_by_seller(self):
        rows = {r['store_name']: r for r in self.client.get('/api/reports/sellers/').data['results']}
        self.assertEqual((float(rows['Аптека']['gmv']), float(rows['Аптека']['commission'])), (200, 30))
        self.assertEqual((float(rows['Овощи']['gmv']), float(rows['Овощи']['returns_amount'])), (150, 50))

    def test_by_category_with_path(self):
        rows = self.client.get('/api/reports/categories/').data['results']
        self.assertEqual([(r['category'], r['share']) for r in rows], [('Лекарства → Спреи', 57.1), ('Еда', 42.9)])

    def test_top_products_and_deliveries(self):
        data = self.client.get('/api/reports/dashboard/').data
        self.assertEqual([(p['name'], p['items_sold']) for p in data['top_products']], [('Томат', 3), ('Спрей', 2)])
        d = data['deliveries']
        self.assertEqual((d['total'], d['courier'], d['delivered_share']), (2, 2, 100.0))
        self.assertIsNotNone(d['average_hours'])

    def test_csv_export(self):
        r = self.client.get('/api/reports/sellers/', {'export': 'csv'})
        self.assertEqual(r['Content-Type'], 'text/csv; charset=utf-8')
        text = r.content.decode('utf-8')
        self.assertTrue(text.startswith('﻿Магазин;Заказов;'))
        self.assertIn('Аптека;1;2;200,00;30,00;170,00;0,00;', text)

    def test_access(self):
        for role, code in [(User.Role.ADMIN, 200), (User.Role.MANAGER, 403), (User.Role.COURIER, 403)]:
            auth(self.client, make_staff(f'{role}-reports@test.ru', role))
            self.assertEqual(self.client.get('/api/reports/dashboard/').status_code, code, role)
        auth(self.client, self.pharmacy)
        self.assertEqual(self.client.get('/api/reports/sellers/').status_code, 403)

    def test_seller_sees_only_own_shop(self):
        auth(self.client, self.pharmacy)
        s = self.client.get('/api/seller/stats/').data
        self.assertEqual((float(s['summary']['gmv']), float(s['summary']['commission'])), (200, 30))
        self.assertEqual([p['name'] for p in s['top_products']], ['Спрей'])
        self.assertNotIn('new_customers', s['summary'])  # данные площадки продавцу не нужны

    def test_bad_params(self):
        self.assertEqual(self.client.get('/api/reports/dashboard/', {'group': 'year'}).status_code, 400)
        self.assertEqual(self.client.get('/api/reports/dashboard/', {'date_from': 'вчера'}).status_code, 400)
