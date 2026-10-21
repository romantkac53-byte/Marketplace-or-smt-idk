"""Артикул товара. Три шага, потому что поле уникальное:
если сразу добавить его со значением по умолчанию, Django присвоил бы ВСЕМ существующим
товарам одно и то же число — и уникальность сломалась бы.
"""
import secrets

from django.db import migrations, models


def fill_articles(apps, schema_editor):
    Product = apps.get_model('catalog', 'Product')
    used = set()
    for product in Product.objects.filter(article__isnull=True):
        while True:
            article = 100_000_000 + secrets.randbelow(900_000_000)
            if article not in used:
                break
        used.add(article)
        product.article = article
        product.save(update_fields=['article'])


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_category_commission_percent'),
    ]

    operations = [
        # 1. Поле без ограничений, у существующих товаров пока пусто
        migrations.AddField(
            model_name='product',
            name='article',
            field=models.PositiveBigIntegerField(null=True, editable=False, verbose_name='Артикул'),
        ),
        # 2. Каждому существующему товару — свой номер
        migrations.RunPython(fill_articles, migrations.RunPython.noop),
        # 3. Теперь можно: обязательное и уникальное
        migrations.AlterField(
            model_name='product',
            name='article',
            field=models.PositiveBigIntegerField(unique=True, editable=False, verbose_name='Артикул'),
        ),
    ]
