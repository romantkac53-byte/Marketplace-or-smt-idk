"""Расчёт отчётов. Всё считается агрегатами в базе данных (SUM, COUNT, GROUP BY), а не перебором в Python.

Определения:
  • продажи периода — позиции заказов, ОПЛАЧЕННЫХ в период (Payment.paid_at), кроме отменённых подзаказов;
  • оборот (GMV) — Σ цена_со_скидкой × количество;
  • комиссия — Σ round(цена × количество × процент / 100, 2) — так же, как в кабинете продавца;
  • заказы — оплаченные в период заказы, в которых что-то реально продано (не всё отменено);
  • возвраты — принятые возвраты (статус «completed»), оформленные в период.
Все функции принимают seller — тогда считают только по одному магазину (сводка в кабинете продавца).
"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce, Round, TruncDay, TruncMonth, TruncWeek
from django.utils import timezone

from catalog.models import Category, Product
from delivery.models import Delivery
from orders.models import Order, OrderItem, SellerOrder
from returns.models import ReturnRequest
from reviews.models import Review
from users.models import Customer, Seller

MONEY = DecimalField(max_digits=14, decimal_places=2)
ZERO = Decimal('0.00')
GMV = Coalesce(Sum(F('price') * F('quantity'), output_field=MONEY), ZERO, output_field=MONEY)
COMMISSION = Coalesce(
    Sum(Round(F('price') * F('quantity') * F('commission_percent') / 100, 2), output_field=MONEY),
    ZERO, output_field=MONEY,
)
QUANTITY = Coalesce(Sum('quantity'), 0)


class Period:
    """Период отчёта: даты включительно. По умолчанию — последние 30 дней."""

    def __init__(self, date_from=None, date_to=None):
        today = timezone.localdate()
        self.date_to = date_to or today
        self.date_from = date_from or self.date_to - timedelta(days=29)
        if self.date_from > self.date_to:
            self.date_from, self.date_to = self.date_to, self.date_from
        tz = timezone.get_current_timezone()
        self.start = datetime.combine(self.date_from, time.min, tzinfo=tz)
        self.end = datetime.combine(self.date_to + timedelta(days=1), time.min, tzinfo=tz)  # конец — не включая

    @property
    def days(self):
        return (self.date_to - self.date_from).days + 1

    def previous(self):
        """Предыдущий период такой же длины — для сравнения «было / стало»."""
        return Period(self.date_from - timedelta(days=self.days), self.date_from - timedelta(days=1))

    def as_dict(self):
        return {'date_from': self.date_from.isoformat(), 'date_to': self.date_to.isoformat(), 'days': self.days}


def sold_items(period, seller=None):
    """Позиции, проданные в период (оплачены, подзаказ не отменён)."""
    qs = OrderItem.objects.filter(
        seller_order__order__payment__paid_at__gte=period.start,
        seller_order__order__payment__paid_at__lt=period.end,
    ).exclude(seller_order__status=SellerOrder.Status.CANCELLED)
    return qs.filter(seller_order__seller=seller) if seller else qs


def completed_returns(period, seller=None):
    qs = ReturnRequest.objects.filter(status=ReturnRequest.Status.COMPLETED,
                                      created_at__gte=period.start, created_at__lt=period.end)
    return qs.filter(order_item__seller_order__seller=seller) if seller else qs


def money(value):
    """Деньги всегда с двумя знаками: SQLite возвращает сумму 200 как Decimal('200'), а нужно 200.00."""
    return Decimal(value or 0).quantize(Decimal('0.01'))


def _ratio(part, whole):
    return round(float(part) / float(whole) * 100, 1) if whole else 0.0


def summary(period, seller=None):
    """Главные показатели периода."""
    items = sold_items(period, seller)
    totals = items.aggregate(gmv=GMV, commission=COMMISSION, quantity=QUANTITY,
                             orders=Count('seller_order__order', distinct=True))
    returns = completed_returns(period, seller).aggregate(
        amount=Coalesce(Sum('refund_amount'), ZERO, output_field=MONEY), quantity=Coalesce(Sum('quantity'), 0))

    paid_suborders = SellerOrder.objects.filter(order__payment__paid_at__gte=period.start,
                                                order__payment__paid_at__lt=period.end)
    if seller:
        paid_suborders = paid_suborders.filter(seller=seller)
    suborders = paid_suborders.aggregate(total=Count('id'),
                                         cancelled=Count('id', filter=Q(status=SellerOrder.Status.CANCELLED)))

    gmv, commission = money(totals['gmv']), money(totals['commission'])
    data = {
        'gmv': gmv,
        'commission': commission,
        'seller_payout': gmv - commission,
        'orders': totals['orders'],
        'items_sold': totals['quantity'],
        'average_check': (gmv / totals['orders']).quantize(Decimal('0.01')) if totals['orders'] else ZERO,
        'returns_amount': money(returns['amount']),
        'returns_quantity': returns['quantity'],
        'returns_share': _ratio(returns['amount'], gmv),
        'cancelled_share': _ratio(suborders['cancelled'], suborders['total']),
    }
    if seller is None:
        data.update({
            'new_customers': Customer.objects.filter(user__date_joined__gte=period.start, user__date_joined__lt=period.end).count(),
            'new_sellers': Seller.objects.filter(user__date_joined__gte=period.start, user__date_joined__lt=period.end).count(),
            'pending_sellers': Seller.objects.filter(status='pending').count(),
            'low_stock_products': Product.objects.filter(is_active=True, stock__lt=F('reserved') + 5).count(),
        })
    return data


TRUNC = {'day': TruncDay, 'week': TruncWeek, 'month': TruncMonth}


def _buckets(period, group):
    """Все интервалы периода — чтобы на графике были и дни без продаж (с нулём), а не дыры."""
    current = period.date_from
    if group == 'week':
        current -= timedelta(days=current.weekday())  # неделя начинается с понедельника, как в TruncWeek
    elif group == 'month':
        current = current.replace(day=1)
    while current <= period.date_to:
        yield current
        if group == 'day':
            current += timedelta(days=1)
        elif group == 'week':
            current += timedelta(days=7)
        else:
            current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)


def sales_series(period, group='day', seller=None):
    """Продажи по дням / неделям / месяцам."""
    rows = (sold_items(period, seller)
            .annotate(bucket=TRUNC[group]('seller_order__order__payment__paid_at'))
            .values('bucket')
            .annotate(gmv=GMV, commission=COMMISSION, orders=Count('seller_order__order', distinct=True))
            .order_by('bucket'))
    by_date = {timezone.localtime(r['bucket']).date() if hasattr(r['bucket'], 'hour') else r['bucket']: r for r in rows}
    return [{
        'date': bucket.isoformat(),
        'gmv': money(by_date.get(bucket, {}).get('gmv')),
        'commission': money(by_date.get(bucket, {}).get('commission')),
        'orders': by_date.get(bucket, {}).get('orders', 0),
    } for bucket in _buckets(period, group)]


def by_seller(period):
    """Продажи по магазинам."""
    rows = list(sold_items(period)
                .values('seller_order__seller_id', 'seller_order__seller__store_name')
                .annotate(gmv=GMV, commission=COMMISSION, quantity=QUANTITY,
                          orders=Count('seller_order__order', distinct=True))
                .order_by('-gmv'))
    returns = dict(completed_returns(period)
                   .values_list('order_item__seller_order__seller_id')
                   .annotate(total=Sum('refund_amount')))
    ratings = dict(Review.objects.filter(is_published=True)
                   .values_list('product__seller_id').annotate(avg=Avg('rating')))
    return [{
        'seller_id': r['seller_order__seller_id'],
        'store_name': r['seller_order__seller__store_name'],
        'orders': r['orders'],
        'items_sold': r['quantity'],
        'gmv': money(r['gmv']),
        'commission': money(r['commission']),
        'seller_payout': money(r['gmv'] - r['commission']),
        'returns_amount': money(returns.get(r['seller_order__seller_id'])),
        'rating': round(ratings[r['seller_order__seller_id']], 1) if r['seller_order__seller_id'] in ratings else None,
    } for r in rows]


def by_category(period):
    """Продажи по категориям (конечным — тем, где лежат товары) с полным путём «Лекарства → Спреи»."""
    rows = list(sold_items(period).values('product__category_id')
                .annotate(gmv=GMV, commission=COMMISSION, quantity=QUANTITY).order_by('-gmv'))
    categories = Category.objects.in_bulk([r['product__category_id'] for r in rows])
    total = sum((r['gmv'] for r in rows), ZERO)
    return [{
        'category_id': r['product__category_id'],
        'category': str(categories[r['product__category_id']]),
        'items_sold': r['quantity'],
        'gmv': money(r['gmv']),
        'commission': money(r['commission']),
        'share': _ratio(r['gmv'], total),
    } for r in rows]


def top_products(period, seller=None, limit=10):
    rows = (sold_items(period, seller).values('product_id')
            .annotate(gmv=GMV, quantity=QUANTITY).order_by('-quantity', '-gmv')[:limit])
    products = Product.objects.select_related('seller').in_bulk([r['product_id'] for r in rows])
    return [{
        'product_id': r['product_id'],
        'name': products[r['product_id']].name,
        'store_name': products[r['product_id']].seller.store_name,
        'items_sold': r['quantity'],
        'gmv': money(r['gmv']),
    } for r in rows]


def deliveries(period):
    """Доставка: посылки, созданные в период (подзаказ собран), по статусам и способам."""
    qs = Delivery.objects.filter(created_at__gte=period.start, created_at__lt=period.end)
    statuses = dict(qs.values_list('status').annotate(n=Count('id')))
    by_type = dict(qs.values_list('seller_order__order__delivery_type').annotate(n=Count('id')))
    delivered = qs.filter(status=Delivery.Status.DELIVERED).annotate(
        duration=ExpressionWrapper(F('delivered_at') - F('seller_order__order__payment__paid_at'), output_field=DurationField()))
    avg = delivered.aggregate(avg=Avg('duration'))['avg']
    total = sum(statuses.values())
    return {
        'total': total,
        'by_status': [{'status': s.value, 'label': s.label, 'count': statuses.get(s.value, 0)} for s in Delivery.Status],
        'courier': by_type.get(Order.DeliveryType.COURIER.value, 0),
        'pickup': by_type.get(Order.DeliveryType.PICKUP.value, 0),
        'delivered_share': _ratio(statuses.get(Delivery.Status.DELIVERED.value, 0), total),
        'average_hours': round(avg.total_seconds() / 3600, 1) if avg else None,
    }
