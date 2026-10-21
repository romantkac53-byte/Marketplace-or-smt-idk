"""Кабинет сотрудника склада: сборка подзаказов, остатки, приход/списание/инвентаризация, приёмка возвратов."""
from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from catalog.filters import ArticleSearchFilter
from catalog.models import Product
from catalog.seller_api import StockMovementSerializer
from marketplace.permissions import has_role
from orders.models import SellerOrder
from returns.models import ReturnRequest
from returns.views import ReturnSerializer
from users.models import User

from .models import StockMovement, move_stock

IsWarehouse = has_role(User.Role.WAREHOUSE)


# ---------- Сборка подзаказов ----------

class AssemblyItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    quantity = serializers.IntegerField()


class AssemblySerializer(serializers.ModelSerializer):
    """Подзаказ для сборщика: что собрать и куда отправить. Ни цен, ни данных покупателя."""
    order_id = serializers.IntegerField()
    seller = serializers.CharField(source='seller.store_name')
    status_display = serializers.CharField(source='get_status_display')
    delivery_type = serializers.CharField(source='order.get_delivery_type_display')
    pickup_point = serializers.StringRelatedField(source='order.pickup_point')
    items = AssemblyItemSerializer(many=True)
    paid_at = serializers.DateTimeField(source='order.payment.paid_at')

    class Meta:
        model = SellerOrder
        fields = ('id', 'order_id', 'seller', 'status', 'status_display', 'delivery_type', 'pickup_point',
                  'items', 'paid_at')


@extend_schema_view(
    list=extend_schema(tags=['Склад'], summary='Очередь сборки (по умолчанию: подтверждённые и собираемые)'),
)
class AssemblyViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsWarehouse]
    serializer_class = AssemblySerializer
    filterset_fields = ['status', 'seller']
    ordering = ['order__payment__paid_at']  # первым — то, что оплатили раньше

    def get_queryset(self):
        qs = SellerOrder.objects.select_related('seller', 'order__payment', 'order__pickup_point') \
            .prefetch_related('items')
        if self.action == 'list' and 'status' not in self.request.query_params:
            qs = qs.filter(status__in=[SellerOrder.Status.CONFIRMED, SellerOrder.Status.ASSEMBLING])
        return qs

    def _change(self, request, new_status):
        seller_order = self.get_object()
        seller_order.change_status(new_status, changed_by=request.user)
        return Response(self.get_serializer(self.get_queryset().get(pk=seller_order.pk)).data)

    @extend_schema(tags=['Склад'], summary='Начать сборку', request=None, responses=AssemblySerializer)
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        return self._change(request, SellerOrder.Status.ASSEMBLING)

    @extend_schema(tags=['Склад'], summary='Собран — создаётся доставка, посылка ждёт курьера',
                   request=None, responses=AssemblySerializer)
    @action(detail=True, methods=['post'])
    def ready(self, request, pk=None):
        return self._change(request, SellerOrder.Status.READY)


# ---------- Остатки и операции ----------

class StockLevelSerializer(serializers.ModelSerializer):
    seller = serializers.CharField(source='seller.store_name')
    available = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'article', 'name', 'seller', 'stock', 'reserved', 'available', 'is_active')


@extend_schema(tags=['Склад'], summary='Остатки товаров (?low=5 — где доступно меньше 5)')
class StockLevelListView(generics.ListAPIView):
    permission_classes = [IsWarehouse]
    serializer_class = StockLevelSerializer
    filter_backends = [DjangoFilterBackend, ArticleSearchFilter, OrderingFilter]
    filterset_fields = ['seller', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'stock', 'reserved']
    ordering = ['name']

    def get_queryset(self):
        qs = Product.objects.select_related('seller')
        low = self.request.query_params.get('low')
        if low and low.isdigit():
            qs = qs.filter(stock__lt=F('reserved') + int(low))  # доступно (stock − reserved) < low
        return qs


class StockOperationSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), source='product')
    type = serializers.ChoiceField(choices=[(t.value, t.label) for t in StockMovement.MANUAL_TYPES])
    quantity = serializers.IntegerField(min_value=0, help_text='Для инвентаризации — фактический остаток')
    comment = serializers.CharField(max_length=255, required=False, allow_blank=True)


@extend_schema_view(
    get=extend_schema(tags=['Склад'], summary='Журнал движения товаров'),
    post=extend_schema(tags=['Склад'], summary='Приход, списание или инвентаризация',
                       request=StockOperationSerializer, responses={201: StockMovementSerializer}),
)
class StockMovementListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsWarehouse]
    queryset = StockMovement.objects.select_related('product')
    filterset_fields = ['product', 'type', 'seller_order']
    ordering = ['-created_at', '-id']

    def get_serializer_class(self):
        return StockOperationSerializer if self.request.method == 'POST' else StockMovementSerializer

    def create(self, request):
        serializer = StockOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # move_stock сам проверит: нельзя списать зарезервированное, остаток не уйдёт в минус
        movement = move_stock(data['product'], data['type'], data['quantity'],
                              created_by=request.user, comment=data.get('comment', ''))
        return Response(StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED)


# ---------- Приёмка возвратов ----------

@extend_schema_view(
    list=extend_schema(tags=['Склад'], summary='Одобренные возвраты — ждут приёмки товара'),
)
class WarehouseReturnViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsWarehouse]
    serializer_class = ReturnSerializer
    ordering = ['created_at']

    def get_queryset(self):
        return ReturnRequest.objects.filter(status=ReturnRequest.Status.APPROVED).select_related(
            'order_item__seller_order__seller', 'order_item__seller_order__order').prefetch_related('history')

    @extend_schema(tags=['Склад'], summary='Товар принят — вернуть на склад (брак — списать), деньги покупателю',
                   request=None, responses=ReturnSerializer)
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        return_request = self.get_object()
        return_request.complete(changed_by=request.user)
        return Response(ReturnSerializer(ReturnRequest.objects.get(pk=return_request.pk)).data)
