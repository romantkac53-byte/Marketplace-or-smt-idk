from rest_framework.test import APITestCase

from marketplace.testing import auth, make_customer, make_delivered_order, make_paid_order, make_product, make_seller


class ReviewApiTests(APITestCase):
    def setUp(self):
        self.seller = make_seller()
        self.product = make_product(self.seller, price=100)
        self.buyer = make_customer()
        auth(self.client, self.buyer)

    def test_only_after_delivery(self):
        make_paid_order(self.buyer, (self.product, 1))
        r = self.client.post('/api/reviews/', {'product_id': self.product.pk, 'rating': 5})
        self.assertEqual(r.status_code, 400)
        self.assertIn('полученный', r.data['detail'])

    def test_create_edit_delete(self):
        order = make_delivered_order(self.buyer, (self.product, 1))
        order_data = self.client.get(f'/api/orders/{order.pk}/').data
        self.assertTrue(order_data['seller_orders'][0]['can_review'])

        r = self.client.post('/api/reviews/', {'product_id': self.product.pk, 'rating': 4, 'text': 'норм'})
        self.assertEqual(r.status_code, 201, r.data)
        review_id = r.data['id']
        r = self.client.patch(f'/api/reviews/{review_id}/', {'rating': 5})
        self.assertEqual((r.data['rating'], r.data['text']), (5, 'норм'))
        self.assertEqual(self.client.get(f'/api/products/{self.product.pk}/').data['rating'], 5.0)
        self.assertEqual(self.client.delete(f'/api/reviews/{review_id}/').status_code, 204)

    def test_rating_range(self):
        make_delivered_order(self.buyer, (self.product, 1))
        r = self.client.post('/api/reviews/', {'product_id': self.product.pk, 'rating': 6})
        self.assertEqual(r.status_code, 400)

    def test_seller_replies_only_to_own_products(self):
        make_delivered_order(self.buyer, (self.product, 1))
        review_id = self.client.post('/api/reviews/', {'product_id': self.product.pk, 'rating': 3}).data['id']

        auth(self.client, make_seller('other@test.ru', 'Чужой'))
        self.assertEqual(self.client.post(f'/api/seller/reviews/{review_id}/reply/', {'text': 'x'}).status_code, 404)

        auth(self.client, self.seller)
        self.assertEqual(self.client.get('/api/seller/reviews/').data['count'], 1)
        r = self.client.post(f'/api/seller/reviews/{review_id}/reply/', {'text': 'Спасибо!'})
        self.assertEqual(r.data['seller_reply'], 'Спасибо!')
        public = self.client.get(f'/api/products/{self.product.pk}/reviews/').data['results'][0]
        self.assertEqual(public['seller_reply'], 'Спасибо!')


class ManagerReviewApiTests(APITestCase):
    def test_hide_affects_rating(self):
        from marketplace.testing import make_staff
        from users.models import User
        product = make_product(make_seller(), price=100)
        buyer = make_customer()
        make_delivered_order(buyer, (product, 1))
        review = buyer.customer.leave_review(product, 1, 'спам')
        auth(self.client, make_staff('manager@test.ru', User.Role.MANAGER))
        self.client.post(f'/api/manager/reviews/{review.pk}/hide/')
        self.assertIsNone(self.client.get(f'/api/products/{product.pk}/').data['rating'])
        self.client.post(f'/api/manager/reviews/{review.pk}/publish/')
        self.assertEqual(self.client.get(f'/api/products/{product.pk}/').data['rating'], 1.0)
