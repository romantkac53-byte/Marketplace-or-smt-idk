from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from delivery.models import PickupPoint
from delivery.serializers import CustomerDeliverySerializer, PickupPointSerializer
from payments.serializers import PaymentSerializer

from .models import Order, OrderItem, SellerOrder, StatusHistory


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(source='calculate_subtotal', max_digits=12, decimal_places=2)
    promotion = serializers.StringRelatedField()

    class Meta:
        model = OrderItem
        fields = ('id', 'product_id', 'product_name', 'original_price', 'price', 'promotion', 'quantity',
                  'subtotal')


class StatusHistorySerializer(serializers.ModelSerializer):
    seller_order_id = serializers.IntegerField(allow_null=True)
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = StatusHistory
        fields = ('seller_order_id', 'old_status', 'new_status', 'status_display', 'changed_at', 'comment')

    def get_status_display(self, entry) -> str:
        status_class = SellerOrder.Status if entry.seller_order_id else Order.Status
        return status_class(entry.new_status).label


class CustomerOrderItemSerializer(OrderItemSerializer):
    returnable_quantity = serializers.SerializerMethodField()

    class Meta(OrderItemSerializer.Meta):
        fields = OrderItemSerializer.Meta.fields + ('returnable_quantity',)

    def get_returnable_quantity(self, item) -> int:
        """Сколько штук можно вернуть сейчас — для кнопки «Вернуть» (0 — кнопку не показывать).
        Считается по уже загруженным данным, без запросов к базе на каждую позицию."""
        from returns.models import RETURN_DAYS, ReturnRequest

        seller_order = item.seller_order
        delivery = getattr(seller_order, 'delivery', None)
        if seller_order.status != SellerOrder.Status.DELIVERED:
            return 0
        received_at = delivery.delivered_at if delivery and delivery.delivered_at else seller_order.updated_at
        if timezone.now() > received_at + timedelta(days=RETURN_DAYS):
            return 0
        taken = sum(r.quantity for r in item.returns.all() if r.status in ReturnRequest.ACTIVE_STATUSES)
        return item.quantity - taken


class CustomerSellerOrderSerializer(serializers.ModelSerializer):
    """Подзаказ глазами покупателя: магазин, статус, товары, доставка."""

    seller = serializers.CharField(source='seller.store_name')
    status_display = serializers.CharField(source='get_status_display')
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    items = CustomerOrderItemSerializer(many=True)
    delivery = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_review = serializers.SerializerMethodField()

    class Meta:
        model = SellerOrder
        fields = ('id', 'seller', 'status', 'status_display', 'subtotal', 'items', 'delivery', 'can_cancel',
                  'can_review')

    def get_delivery(self, seller_order) -> dict | None:
        delivery = getattr(seller_order, 'delivery', None)
        return CustomerDeliverySerializer(delivery).data if delivery else None

    def get_can_cancel(self, seller_order) -> bool:
        # Отменить свою часть можно, пока посылка не передана в доставку
        return SellerOrder.Status.CANCELLED in SellerOrder.TRANSITIONS[seller_order.status] \
            and seller_order.status not in SellerOrder.SHIPPED_STATUSES

    def get_can_review(self, seller_order) -> bool:
        # Отзыв можно оставить на товары, которые покупатель получил
        return seller_order.status == SellerOrder.Status.DELIVERED


class OrderListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display')
    delivery_type_display = serializers.CharField(source='get_delivery_type_display')
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_status = serializers.CharField(source='payment.status', default=None)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ('id', 'created_at', 'status', 'status_display', 'delivery_type', 'delivery_type_display',
                  'total_amount', 'payment_status', 'items_count')

    def get_items_count(self, order) -> int:
        return sum(item.quantity for so in order.seller_orders.all() for item in so.items.all())


class OrderDetailSerializer(OrderListSerializer):
    pickup_point = PickupPointSerializer()
    payment = PaymentSerializer()
    seller_orders = CustomerSellerOrderSerializer(many=True)
    history = serializers.SerializerMethodField()

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + ('delivery_address', 'pickup_point', 'payment',
                                                    'seller_orders', 'history')

    def get_history(self, order) -> list[dict]:
        return StatusHistorySerializer(order.history.all(), many=True).data


class PlaceOrderSerializer(serializers.Serializer):
    """Оформление заказа из корзины."""

    delivery_type = serializers.ChoiceField(choices=Order.DeliveryType.choices)
    delivery_address = serializers.CharField(max_length=255, required=False, allow_blank=True,
                                             help_text='Для курьера. Пусто — адрес из профиля')
    pickup_point_id = serializers.PrimaryKeyRelatedField(
        queryset=PickupPoint.objects.filter(is_active=True), source='pickup_point', required=False,
        help_text='Для доставки в пункт выдачи',
    )

    def validate(self, data):
        if data['delivery_type'] == Order.DeliveryType.PICKUP and not data.get('pickup_point'):
            raise serializers.ValidationError({'pickup_point_id': 'Выберите пункт выдачи'})
        if data['delivery_type'] == Order.DeliveryType.COURIER:
            data.pop('pickup_point', None)  # для курьерской доставки пункт выдачи не нужен
        return data


class CommentSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=255, required=False, allow_blank=True)
