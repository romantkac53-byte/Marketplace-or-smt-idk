"""Общие заготовки для автотестов API: пользователи, магазины, товары, вход по токену."""
from catalog.models import Category, Product
from users.models import Customer, Seller, User

PASSWORD = 'Str0ng-pass-123'


def make_customer(email='buyer@test.ru', **profile):
    user = User.objects.create_user(email=email, password=PASSWORD, role=User.Role.CUSTOMER)
    Customer.objects.create(user=user, address=profile.get('address', 'ул. Тестовая, 1'))
    return user


def make_seller(email='shop@test.ru', store_name='Тест-магазин', status='active'):
    user = User.objects.create_user(email=email, password=PASSWORD, role=User.Role.SELLER)
    Seller.objects.create(user=user, store_name=store_name, status=status)
    return user


def make_staff(email, role):
    return User.objects.create_user(email=email, password=PASSWORD, role=role)


def make_product(seller_user, category=None, name='Товар', price=100, stock=10, **extra):
    if category is None:
        category, _ = Category.objects.get_or_create(slug='test-cat', defaults={'name': 'Тест'})
    product = Product.objects.create(seller=seller_user.seller, category=category, name=name, price=price, **extra)
    if stock:
        product.update_stock(stock)
    return product


def make_paid_order(customer_user, *products_qty):
    """Оплаченный заказ: make_paid_order(buyer, (product, 2), (other, 1))."""
    from payments.models import top_up

    customer = customer_user.customer
    for product, qty in products_qty:
        customer.add_to_cart(product, qty)
    order = customer.place_order()
    top_up(customer, order.total_amount)
    order.pay()
    return order


def make_delivered_order(customer_user, *products_qty):
    """Заказ, прошедший весь путь до получения покупателем — для отзывов и возвратов."""
    from delivery.models import Delivery
    from orders.models import SellerOrder

    order = make_paid_order(customer_user, *products_qty)
    courier = User.objects.filter(role=User.Role.COURIER).first() or make_staff('courier@test.ru', User.Role.COURIER)
    for seller_order in order.seller_orders.all():
        for status in (SellerOrder.Status.CONFIRMED, SellerOrder.Status.ASSEMBLING, SellerOrder.Status.READY):
            seller_order.change_status(status)
        delivery = Delivery.objects.get(seller_order=seller_order)
        delivery.assign_courier(courier)
        delivery.pick_up()
        delivery.hand_over()
    return order


def auth(client, user):
    """Логинит тестовый клиент по JWT, как это будет делать фронтенд."""
    response = client.post('/api/auth/login/', {'email': user.email, 'password': PASSWORD}, format='json')
    assert response.status_code == 200, response.data
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
    return response.data
