from rest_framework.test import APITestCase

from marketplace.testing import PASSWORD, auth, make_customer

from .models import User


class AuthApiTests(APITestCase):
    def test_register_customer_returns_tokens_and_profile(self):
        r = self.client.post('/api/auth/register/customer/', {
            'email': 'new@test.ru', 'password': PASSWORD, 'accept_terms': True, 'first_name': 'Анна', 'address': 'ул. Мира, 5',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn('access', r.data['tokens'])
        self.assertEqual(r.data['user']['role'], 'customer')
        self.assertEqual(r.data['user']['customer']['address'], 'ул. Мира, 5')
        self.assertNotIn('seller', r.data['user'])

    def test_terms_must_be_accepted(self):
        for payload in ({}, {'accept_terms': False}):
            r = self.client.post('/api/auth/register/customer/', {'email': 'x@test.ru', 'password': PASSWORD, **payload},
                                 format='json')
            self.assertEqual(r.status_code, 400)
            self.assertIn('accept_terms', r.data)
        self.assertFalse(User.objects.filter(email='x@test.ru').exists())

    def test_terms_acceptance_time_saved(self):
        self.client.post('/api/auth/register/customer/', {'email': 'ok@test.ru', 'password': PASSWORD, 'accept_terms': True},
                         format='json')
        self.assertIsNotNone(User.objects.get(email='ok@test.ru').terms_accepted_at)

    def test_register_seller_is_pending(self):
        r = self.client.post('/api/auth/register/seller/', {
            'email': 'shop@test.ru', 'password': PASSWORD, 'store_name': 'Аптека', 'accept_terms': True,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['user']['seller']['status'], 'pending')

    def test_duplicate_email_and_weak_password_rejected(self):
        make_customer('taken@test.ru')
        r = self.client.post('/api/auth/register/customer/', {'email': 'TAKEN@test.ru', 'password': '123', 'accept_terms': True},
                             format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('email', r.data)
        self.assertIn('password', r.data)

    def test_login_wrong_password(self):
        make_customer()
        r = self.client.post('/api/auth/login/', {'email': 'buyer@test.ru', 'password': 'wrong'}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_me_requires_auth_and_updates_profile(self):
        self.assertEqual(self.client.get('/api/me/').status_code, 401)
        user = make_customer()
        auth(self.client, user)
        r = self.client.patch('/api/me/', {'first_name': 'Иван', 'customer': {'phone': '+79990001122'}},
                              format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['first_name'], 'Иван')
        self.assertEqual(r.data['customer']['phone'], '+79990001122')

    def test_balance_and_role_are_read_only(self):
        user = make_customer()
        auth(self.client, user)
        self.client.patch('/api/me/', {'role': 'admin', 'customer': {'balance': '1000000'}}, format='json')
        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertEqual(user.customer.balance, 0)

    def test_logout_blacklists_refresh(self):
        user = make_customer()
        tokens = auth(self.client, user)
        self.assertEqual(self.client.post('/api/auth/logout/', {'refresh': tokens['refresh']}).status_code, 200)
        r = self.client.post('/api/auth/refresh/', {'refresh': tokens['refresh']})
        self.assertEqual(r.status_code, 401)

    def test_password_change(self):
        user = make_customer()
        auth(self.client, user)
        r = self.client.post('/api/me/password/', {'old_password': 'wrong', 'new_password': 'N3w-pass-456!'})
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/me/password/', {'old_password': PASSWORD, 'new_password': 'N3w-pass-456!'})
        self.assertEqual(r.status_code, 204)
        user.refresh_from_db()
        self.assertTrue(user.check_password('N3w-pass-456!'))


class LoginByUsernameTests(APITestCase):
    """Регистрация и вход по логину — без email."""

    def register(self, kind='customer', **data):
        payload = {'password': PASSWORD, 'accept_terms': True, **data}
        return self.client.post(f'/api/auth/register/{kind}/', payload, format='json')

    def login(self, **credentials):
        return self.client.post('/api/auth/login/', {'password': PASSWORD, **credentials}, format='json')

    def test_register_by_login_without_email(self):
        r = self.register(login='tester1', first_name='')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['user']['login'], 'tester1')
        self.assertIsNone(r.data['user']['email'])
        user = User.objects.get(login='tester1')
        self.assertIsNone(user.email)  # NULL, а не '' — иначе второй такой же пользователь нарушил бы уникальность
        self.assertEqual(self.register(kind='seller', login='shop2', store_name='Магазин').status_code, 201)

    def test_login_by_login_and_by_email(self):
        self.register(login='Tester1')
        self.assertEqual(self.login(login='tester1').status_code, 200)       # регистр не важен
        self.assertEqual(self.login(email='TESTER1').status_code, 200)       # логин в поле email — тоже найдёт
        self.assertEqual(self.login(login='tester1', password='wrong-pass').status_code, 401)
        make_customer('buyer@test.ru')
        self.assertEqual(self.login(email='buyer@test.ru').status_code, 200)  # старый вход по email не сломан
        r = self.client.post('/api/auth/login/', {'password': PASSWORD}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('login', r.data)

    def test_login_must_be_unique_and_valid(self):
        self.register(login='tester1')
        for bad in ('TESTER1', 'ab', 'a@b', 'с кириллицей', 'x' * 31):
            r = self.register(login=bad)
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn('login', r.data)
        r = self.register()  # ни email, ни логина
        self.assertEqual(r.status_code, 400)
        self.assertIn('login', r.data)

    def test_blocked_user_cannot_login(self):
        self.register(login='tester1')
        User.objects.filter(login='tester1').update(is_active=False)
        self.assertEqual(self.login(login='tester1').status_code, 401)

    def test_admin_login_page_accepts_login(self):
        User.objects.create_superuser(login='boss', password=PASSWORD)
        self.assertTrue(self.client.login(username='boss', password=PASSWORD))

    def test_review_author_shows_login_not_email(self):
        user = User.objects.create_user(login='nick', password=PASSWORD)
        self.assertEqual(user.public_name, 'nick')
        self.assertEqual(str(user), 'nick')
        self.assertEqual(User.objects.create_user(email='anna@test.ru').public_name, 'anna')
