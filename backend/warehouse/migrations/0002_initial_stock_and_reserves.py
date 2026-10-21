from django.db import migrations
from django.db.models import Sum

# Подзаказы, товар которых ещё физически на складе
NOT_SHIPPED = ['new', 'confirmed', 'assembling', 'ready']


def forwards(apps, schema_editor):
    """До складского учёта stock означал «доступно»: товар списывался сразу при оформлении.
    Теперь stock — физический остаток, а неотгруженные заказы — это резерв."""
    Product = apps.get_model('catalog', 'Product')
    OrderItem = apps.get_model('orders', 'OrderItem')
    StockMovement = apps.get_model('warehouse', 'StockMovement')

    for product in Product.objects.all():
        reserved = OrderItem.objects.filter(
            product=product, seller_order__status__in=NOT_SHIPPED,
        ).aggregate(total=Sum('quantity'))['total'] or 0
        product.stock += reserved  # эти единицы ещё лежат на складе
        product.reserved = reserved
        product.save(update_fields=['stock', 'reserved'])
        StockMovement.objects.create(
            product=product, type='inventory', quantity=product.stock,
            stock_delta=product.stock, reserved_delta=reserved,
            stock_after=product.stock, reserved_after=reserved,
            comment='Остатки на момент запуска складского учёта',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('warehouse', '0001_initial'),
        ('catalog', '0004_product_reserved_alter_product_stock'),
        ('orders', '0002_order_delivery_type_order_pickup_point'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
