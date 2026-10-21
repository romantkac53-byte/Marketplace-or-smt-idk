"""Кабинет продавца: подзаказы своего магазина («Обработка заказов» из use case)."""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from marketplace.permissions import IsActiveSeller

from .models import OrderError, OrderItem, SellerOrder
from .serializers import CommentSerializer, StatusHistorySerializer


class SellerOrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(source='calculate_subtotal', max_digits=12, decimal_places=2)
    commission = serializers.DecimalField(max_digits=12, decimal_places=2)
    seller_payout = serializers.DecimalField(max_digits=12, decimal_places=2)
    promotion = serializers.StringRelatedField()

    class Meta:
        model = OrderItem
        fields = ('id', 'product_id', 'product_name', 'original_price', 'price', 'promotion', 'quantity',
                  'subtotal', 'commission_percent', 'commission', 'seller_payout')


class SellerOrderSerializer(serializers.ModelSerializer):
    """Подзаказ глазами продавца. Данных покупателя (адрес, email) нет — доставкой занимается площадка."""

    order_id = serializers.IntegerField()
    created_at = serializers.DateTimeField(source='order.created_at')
    status_display = serializers.CharField(source='get_status_display')
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    commission = serializers.DecimalField(max_digits=12, decimal_places=2)
    seller_payout = serializers.DecimalField(max_digits=12, decimal_places=2)
    delivery_status = serializers.SerializerMethodField()
    items = SellerOrderItemSerializer(many=True)
    history = StatusHistorySerializer(many=True)

    class Meta:
        model = SellerOrder
        fields = ('id', 'order_id', 'created_at', 'status', 'status_display', 'delivery_status', 'subtotal',
                  'commission', 'seller_payout', 'items', 'history')

    def get_delivery_status(self, seller_order) -> str | None:
        delivery = getattr(seller_order, 'delivery', None)
        return delivery.get_status_display() if delivery else None


@extend_schema_view(
    list=extend_schema(tags=['Кабинет продавца'], summary='Заказы моего магазина'),
    retrieve=extend_schema(tags=['Кабинет продавца'], summary='Заказ моего магазина'),
)
class SellerOrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsActiveSeller]
    serializer_class = SellerOrderSerializer
    filterset_fields = ['status']
    ordering_fields = ['order__created_at']
    ordering = ['-order__created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SellerOrder.objects.none()
        # Продавец видит только заказы своего магазина, которые были оплачены:
        # неоплаченные (и отменённые до оплаты) в работу брать нельзя, ему они не нужны
        return SellerOrder.objects.filter(seller=self.request.user.seller, order__payment__paid_at__isnull=False) \
            .select_related('order', 'delivery').prefetch_related('items__promotion', 'history')

    def _fresh(self, seller_order):
        return Response(self.get_serializer(self.get_queryset().get(pk=seller_order.pk)).data)

    @extend_schema(tags=['Кабинет продавца'], summary='Подтвердить заказ (передать на сборку складу)',
                   request=None, responses=SellerOrderSerializer)
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        seller_order = self.get_object()
        seller_order.confirm(changed_by=request.user)
        return self._fresh(seller_order)

    @extend_schema(tags=['Кабинет продавца'], summary='Отменить заказ (например, товара нет) — деньги вернутся покупателю',
                   request=CommentSerializer, responses=SellerOrderSerializer)
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        seller_order = self.get_object()
        if seller_order.status in SellerOrder.SHIPPED_STATUSES:
            raise OrderError('Посылка уже передана в доставку — отменить нельзя')
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.validated_data.get('comment')
        if not comment:
            raise OrderError('Укажите причину отмены — её увидит покупатель')
        seller_order.cancel(changed_by=request.user, comment=f'Отменён продавцом: {comment}')
        return self._fresh(seller_order)
