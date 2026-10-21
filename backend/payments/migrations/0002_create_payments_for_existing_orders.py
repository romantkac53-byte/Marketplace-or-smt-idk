from decimal import Decimal

from django.db import migrations


def create_payments(apps, schema_editor):
    """Заказам, оформленным до появления оплаты, создаём платёж «Ожидает оплаты»."""
    Order = apps.get_model('orders', 'Order')
    OrderItem = apps.get_model('orders', 'OrderItem')
    Payment = apps.get_model('payments', 'Payment')

    for order in Order.objects.filter(payment__isnull=True):
        items = OrderItem.objects.filter(seller_order__order=order).exclude(seller_order__status='cancelled')
        amount = sum((i.price * i.quantity for i in items), Decimal('0'))
        status = 'cancelled' if order.status == 'cancelled' else 'pending'
        Payment.objects.create(order=order, amount=amount, status=status)


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_payments, migrations.RunPython.noop),
    ]
