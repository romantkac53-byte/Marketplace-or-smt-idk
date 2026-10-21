from rest_framework.test import APITestCase

from marketplace.testing import PASSWORD, auth, make_customer, make_seller, make_staff

from .models import User


class ManagerSellerApiTests(APITestCase):
    def test_approve_and_block_seller(self):
        pending = make_seller('new@test.ru', 'Новый', status='pending')
        auth(self.client, make_staff('manager@test.ru', User.Role.MANAGER))
        shops = self.client.get('/api/manager/sellers/', {'status': 'pending'}).data['results']
        self.assertEqual([s['store_name'] for s in shops], ['Новый'])
        r = self.client.post(f'/api/manager/sellers/{pending.seller.pk}/set-status/', {'status': 'blocked'})
        self.assertEqual(r.data['status_display'], 'Заблокирован')

    def test_customer_is_not_manager(self):
        auth(self.client, make_customer())
        self.assertEqual(self.client.get('/api/manager/sellers/').status_code, 403)


class AdminUserApiTests(APITestCase):
    def setUp(self):
        self.admin = make_staff('admin@test.ru', User.Role.ADMIN)
        auth(self.client, self.admin)

    def test_create_staff_and_login(self):
        r = self.client.post('/api/admin/users/', {'email': 'courier@test.ru', 'password': PASSWORD,
                                                   'role': 'courier', 'first_name': 'Иван'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotIn('password', r.data)
        login = self.client.post('/api/auth/login/', {'email': 'courier@test.ru', 'password': PASSWORD})
        self.assertEqual(login.status_code, 200)

    def test_create_staff_by_login_only(self):
        r = self.client.post('/api/admin/users/', {'login': 'courier2', 'password': PASSWORD, 'role': 'courier'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['email'])
        self.assertEqual(self.client.post('/api/auth/login/', {'login': 'courier2', 'password': PASSWORD}).status_code, 200)
        # Тот же логин в другом регистре занят; без email и логина — ошибка
        for payload in ({'login': 'COURIER2'}, {}):
            r = self.client.post('/api/admin/users/', {'password': PASSWORD, 'role': 'courier', **payload})
            self.assertEqual(r.status_code, 400)
            self.assertIn('login', r.data)

    def test_customers_and_sellers_register_themselves(self):
        r = self.client.post('/api/admin/users/', {'email': 'x@test.ru', 'password': PASSWORD, 'role': 'customer'})
        self.assertEqual(r.status_code, 400)

    def test_block_user(self):
        user = make_customer()
        self.client.patch(f'/api/admin/users/{user.pk}/', {'is_active': False})
        r = self.client.post('/api/auth/login/', {'email': user.email, 'password': PASSWORD})
        self.assertEqual(r.status_code, 401)

    def test_cannot_demote_or_block_self(self):
        r = self.client.patch(f'/api/admin/users/{self.admin.pk}/', {'role': 'courier'})
        self.assertEqual(r.status_code, 400)

    def test_manager_is_not_admin(self):
        auth(self.client, make_staff('manager@test.ru', User.Role.MANAGER))
        self.assertEqual(self.client.get('/api/admin/users/').status_code, 403)
