"""Уведомления по событиям. Бизнес-логика заказов, доставки и возвратов уже пишет историю статусов —
здесь мы «подписаны» на появление новых записей истории (сигнал post_save) и по ним создаём уведомления.
Саму логику заказов для этого менять не пришлось."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from delivery.models import Delivery, DeliveryHistory
from orders.models import Order, SellerOrder, StatusHistory
from returns.models import ReturnHistory, ReturnRequest
from reviews.models import Review
from users.models import User

from .models import notify


def _money(value):
    return f'{value:,.2f}'.replace(',', ' ').replace('.', ',') + ' ₽'


@receiver(post_save, sender=StatusHistory)
def order_status_changed(sender, instance, created, **kwargs):
    if not created:
        return
    order = instance.order
    customer = order.customer.user
    link = f'/orders/{order.pk}'

    if instance.seller_order_id is None:  # статус всего заказа
        if instance.new_status == Order.Status.PAID:
            notify(customer, f'Заказ №{order.pk} оплачен — магазины начали сборку', link)
            for seller_order in order.seller_orders.exclude(status=SellerOrder.Status.CANCELLED).select_related('seller__user'):
                notify(seller_order.seller.user,
                       f'Новый заказ №{order.pk} на {_money(seller_order.subtotal)} — подтвердите его', '/seller/orders')
        elif instance.new_status == Order.Status.COMPLETED:
            notify(customer, f'Заказ №{order.pk} выполнен. Оцените покупки — оставьте отзыв', link)
        elif instance.new_status == Order.Status.CANCELLED and instance.changed_by_id != customer.pk:
            notify(customer, f'Заказ №{order.pk} отменён', link)
        return

    # Подзаказ отменил магазин или менеджер — покупателю важно узнать (свою отмену он и так видит;
    # отмену из-за неполученной посылки сообщает уведомление о доставке)
    seller_order = instance.seller_order
    by = instance.changed_by
    if (instance.new_status == SellerOrder.Status.CANCELLED and by is not None
            and (by.pk == seller_order.seller.user_id or by.role in (User.Role.MANAGER, User.Role.ADMIN))):
        reason = f': {instance.comment}' if instance.comment else ''
        notify(customer, f'Магазин «{seller_order.seller.store_name}» отменил свою часть заказа №{order.pk}{reason}. '
                         f'Деньги за неё вернутся на баланс', link)


DELIVERY_TEXTS = {
    Delivery.Status.IN_TRANSIT: 'Посылка из заказа №{order} в пути',
    Delivery.Status.DELIVERED: 'Посылка из заказа №{order} получена. Спасибо за покупку!',
    Delivery.Status.RETURNED: 'Посылка из заказа №{order} не получена и вернулась на склад. Деньги — на балансе',
}


@receiver(post_save, sender=DeliveryHistory)
def delivery_status_changed(sender, instance, created, **kwargs):
    if not created:
        return
    delivery = instance.delivery
    order = delivery.seller_order.order
    customer = order.customer.user
    link = f'/orders/{order.pk}'

    if instance.new_status == Delivery.Status.AT_PICKUP_POINT:
        until = delivery.storage_until.strftime('%d.%m') if delivery.storage_until else ''
        notify(customer, f'Посылка из заказа №{order.pk} ждёт вас в пункте «{order.pickup_point.name}»'
                         f'{f" до {until}" if until else ""}. Код получения — в заказе', link)
    elif instance.new_status in DELIVERY_TEXTS:
        notify(customer, DELIVERY_TEXTS[instance.new_status].format(order=order.pk), link)
    elif instance.new_status == Delivery.Status.ASSIGNED and delivery.courier_id != instance.changed_by_id:
        # Курьера назначил менеджер (а не он сам взял посылку) — курьер должен узнать
        notify(delivery.courier, f'Вам назначена посылка №{delivery.pk} (заказ №{order.pk})', '/staff/courier')


@receiver(post_save, sender=ReturnHistory)
def return_status_changed(sender, instance, created, **kwargs):
    if not created:
        return
    ret = instance.return_request
    customer = ret.customer.user
    status = instance.new_status
    if status == ReturnRequest.Status.REQUESTED:
        notify(ret.order_item.seller_order.seller.user,
               f'Покупатель оформил возврат: «{ret.order_item.product_name}» × {ret.quantity}', '/seller/returns')
    elif status == ReturnRequest.Status.APPROVED:
        notify(customer, f'Возврат №{ret.pk} одобрен — передайте товар в пункт выдачи или курьеру', '/returns')
    elif status == ReturnRequest.Status.REJECTED:
        notify(customer, f'Возврат №{ret.pk} отклонён: {instance.comment}', '/returns')
    elif status == ReturnRequest.Status.COMPLETED:
        notify(customer, f'Возврат №{ret.pk} завершён: {_money(ret.refund_amount)} на балансе', '/returns')


@receiver(post_save, sender=Review)
def review_created(sender, instance, created, **kwargs):
    if created:
        notify(instance.product.seller.user,
               f'Новый отзыв на «{instance.product.name}»: {"★" * instance.rating}', '/seller/reviews')
