from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from marketplace.testing import make_customer, make_product, make_seller
from promotions.models import Promotion

from .models import Category, Characteristic, ProductCharacteristic


class CatalogApiTests(APITestCase):
    def setUp(self):
        self.meds = Category.objects.create(name='Лекарства', slug='meds')
        self.spray = self.meds.add_subcategory('Спреи', 'spray')
        self.food = Category.objects.create(name='Еда', slug='food')
        self.shop = make_seller()
        self.spray_p = make_product(self.shop, self.spray, 'Спрей для носа', price=200, stock=5)
        self.tomato = make_product(self.shop, self.food, 'Томат', price=80, stock=0)

    def names(self, response):
        return [p['name'] for p in response.data['results']]

    def test_catalog_is_public(self):
        r = self.client.get('/api/products/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 2)

    def test_category_tree(self):
        r = self.client.get('/api/categories/')
        meds = next(c for c in r.data if c['slug'] == 'meds')
        self.assertEqual(meds['children'][0]['name'], 'Спреи')

    def test_parent_category_filter_includes_subcategories(self):
        r = self.client.get('/api/products/', {'category': self.meds.pk})
        self.assertEqual(self.names(r), ['Спрей для носа'])

    def test_search_price_stock_filters(self):
        self.assertEqual(self.names(self.client.get('/api/products/', {'search': 'нос'})), ['Спрей для носа'])
        self.assertEqual(self.names(self.client.get('/api/products/', {'price_max': 100})), ['Томат'])
        self.assertEqual(self.names(self.client.get('/api/products/', {'in_stock': 'true'})), ['Спрей для носа'])

    def test_ordering_by_price(self):
        r = self.client.get('/api/products/', {'ordering': 'price'})
        self.assertEqual(self.names(r), ['Томат', 'Спрей для носа'])

    def test_characteristic_filter(self):
        volume = Characteristic.objects.create(name='Объём', unit='мл')
        ProductCharacteristic.objects.create(product=self.spray_p, characteristic=volume, value='20')
        r = self.client.get('/api/products/', {'char': f'{volume.pk}:20'})
        self.assertEqual(self.names(r), ['Спрей для носа'])

    def test_hidden_products_not_shown(self):
        make_product(make_seller('pending@test.ru', status='pending'), self.food, 'От непроверенного продавца')
        make_product(self.shop, self.food, 'Снят с продажи', is_active=False)
        self.assertEqual(self.client.get('/api/products/').data['count'], 2)

    def test_detail_has_price_with_promotion_and_breadcrumbs(self):
        now = timezone.now()
        promo = Promotion.objects.create(name='−10%', discount_type='percent', value=10,
                                         starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=1))
        promo.categories.add(self.meds)
        r = self.client.get(f'/api/products/{self.spray_p.pk}/')
        self.assertEqual(r.data['current_price'], '180.00')
        self.assertEqual([c['name'] for c in r.data['category_path']], ['Лекарства', 'Спреи'])

    def test_product_reviews_only_published(self):
        from reviews.models import Review
        customer = make_customer().customer
        Review.objects.create(product=self.spray_p, customer=customer, rating=5, text='ок')
        Review.objects.create(product=self.spray_p, customer=make_customer('b2@test.ru').customer,
                              rating=1, text='спам', is_published=False)
        r = self.client.get(f'/api/products/{self.spray_p.pk}/reviews/')
        self.assertEqual(r.data['count'], 1)
        listing = self.client.get('/api/products/', {'search': 'нос'}).data['results'][0]
        self.assertEqual((listing['rating'], listing['reviews_count']), (5.0, 1))

    def test_articles_unique_nine_digits(self):
        articles = [make_product(self.shop, self.food, f'Товар {i}').article for i in range(20)]
        self.assertEqual(len(set(articles)), 20)
        self.assertTrue(all(100_000_000 <= a <= 999_999_999 for a in articles))

    def test_search_by_article(self):
        article = self.spray_p.article
        for query in (f'ID{article}', f'id {article}', f'ИД{article}', f'арт. {article}', f' {article} '):
            r = self.client.get('/api/products/', {'search': query})
            self.assertEqual(self.names(r), ['Спрей для носа'], query)
        self.assertEqual(self.client.get('/api/products/', {'search': 'ID999999999'}).data['count'], 0)
        self.assertEqual(self.client.get('/api/products/', {'search': 'ID12'}).data['count'], 0)  # не артикул — обычный поиск
        self.assertEqual(self.client.get(f'/api/products/{self.spray_p.pk}/').data['article'], article)

    def test_seller_and_warehouse_search_by_article(self):
        from marketplace.testing import auth, make_staff
        from users.models import User
        auth(self.client, self.shop)
        r = self.client.get('/api/seller/products/', {'search': f'ID{self.tomato.article}'})
        self.assertEqual([p['name'] for p in r.data['results']], ['Томат'])
        auth(self.client, make_staff('stock@test.ru', User.Role.WAREHOUSE))
        r = self.client.get('/api/warehouse/stock/', {'search': f'ID{self.tomato.article}'})
        self.assertEqual([p['name'] for p in r.data['results']], ['Томат'])

