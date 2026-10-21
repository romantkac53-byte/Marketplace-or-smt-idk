from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from marketplace.permissions import IsCustomer

from .models import Order, OrderError, SellerOrder, place_order
from .serializers import CommentSerializer, OrderDetailSerializer, OrderListSerializer, PlaceOrderSerializer


@extend_schema_view(
    list=extend_schema(tags=['Заказы'], summary='Мои заказы'),
    retrieve=extend_schema(tags=['Заказы'], summary='Заказ: подзаказы, доставка, оплата, история'),
)
class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsCustomer]
    filterset_fields = ['status']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):  # построение документации — пользователя нет
            return Order.objects.none()
        # Изоляция: покупатель видит только свои заказы — чужой заказ отдаст 404
        qs = self.request.user.customer.orders.select_related('payment', 'pickup_point')
        items = SellerOrder.objects.select_related('seller', 'delivery__courier') \
            .prefetch_related('items__promotion', 'items__returns', 'delivery__history')
        return qs.prefetch_related(Prefetch('seller_orders', queryset=items), 'history')

    def get_serializer_class(self):
        return OrderListSerializer if self.action == 'list' else OrderDetailSerializer

    def _detail(self, order, code=status.HTTP_200_OK):
        order = self.get_queryset().get(pk=order.pk)  # свежие данные после изменения
        return Response(OrderDetailSerializer(order, context=self.get_serializer_context()).data, status=code)

    @extend_schema(tags=['Заказы'], summary='Оформить заказ из корзины', request=PlaceOrderSerializer,
                   responses={201: OrderDetailSerializer})
    def create(self, request):
        serializer = PlaceOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        order = place_order(request.user.customer, data.get('delivery_address', ''), data.get('pickup_point'))
        return self._detail(order, status.HTTP_201_CREATED)

    @extend_schema(tags=['Заказы'], summary='Оплатить с баланса', request=None, responses=OrderDetailSerializer)
    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        order = self.get_object()
        order.pay(changed_by=request.user)
        return self._detail(order)

    @extend_schema(tags=['Заказы'], summary='Отменить заказ целиком (если ничего не отправлено)',
                   request=CommentSerializer, responses=OrderDetailSerializer)
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order.cancel(changed_by=request.user, comment=serializer.validated_data.get('comment') or 'Отменён покупателем')
        return self._detail(order)

    @extend_schema(tags=['Заказы'], summary='Отменить часть заказа (подзаказ одного магазина)',
                   request=CommentSerializer, responses=OrderDetailSerializer)
    @action(detail=True, methods=['post'], url_path=r'seller-orders/(?P<seller_order_id>\d+)/cancel')
    def cancel_seller_order(self, request, pk=None, seller_order_id=None):
        order = self.get_object()
        seller_order = get_object_or_404(order.seller_orders, pk=seller_order_id)
        if seller_order.status in SellerOrder.SHIPPED_STATUSES:
            # Покупатель не отменяет посылку в пути — для этого есть отказ при получении и возврат
            raise OrderError('Посылка уже передана в доставку — отменить её нельзя')
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        seller_order.cancel(changed_by=request.user,
                            comment=serializer.validated_data.get('comment') or 'Отменён покупателем')
        return self._detail(order)
