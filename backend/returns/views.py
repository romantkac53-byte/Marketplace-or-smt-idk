from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from marketplace.permissions import IsActiveSeller, IsCustomer, has_role
from orders.models import OrderItem
from users.models import User

from .models import ReturnHistory, ReturnRequest, request_return


class ReturnHistorySerializer(serializers.ModelSerializer):
    status = serializers.CharField(source='new_status')
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = ReturnHistory
        fields = ('status', 'status_display', 'changed_at', 'comment')

    def get_status_display(self, entry) -> str:
        return ReturnRequest.Status(entry.new_status).label


class ReturnSerializer(serializers.ModelSerializer):
    order_item_id = serializers.PrimaryKeyRelatedField(source='order_item', queryset=OrderItem.objects.none())
    order_id = serializers.IntegerField(source='order_item.seller_order.order_id', read_only=True)
    product_name = serializers.CharField(source='order_item.product_name', read_only=True)
    seller = serializers.CharField(source='order_item.seller_order.seller.store_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    history = ReturnHistorySerializer(many=True, read_only=True)

    class Meta:
        model = ReturnRequest
        fields = ('id', 'order_item_id', 'order_id', 'product_name', 'seller', 'quantity', 'reason',
                  'reason_display', 'description', 'status', 'status_display', 'manager_comment', 'amount',
                  'refund_amount', 'created_at', 'history')
        read_only_fields = ('status', 'manager_comment', 'refund_amount', 'created_at')

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request and hasattr(request.user, 'customer'):
            # Выбрать можно только позицию своего заказа — о чужих API даже не сообщает, что они существуют
            fields['order_item_id'].queryset = OrderItem.objects.filter(
                seller_order__order__customer=request.user.customer)
        return fields


def _returns_queryset():
    return ReturnRequest.objects.select_related(
        'order_item__seller_order__seller', 'order_item__seller_order__order',
    ).prefetch_related('history')


@extend_schema_view(
    list=extend_schema(tags=['Возвраты'], summary='Мои возвраты'),
    retrieve=extend_schema(tags=['Возвраты'], summary='Мой возврат'),
    create=extend_schema(tags=['Возвраты'], summary='Оформить возврат (полученный товар, 14 дней)'),
)
class MyReturnViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      viewsets.GenericViewSet):
    permission_classes = [IsCustomer]
    serializer_class = ReturnSerializer
    filterset_fields = ['status']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ReturnRequest.objects.none()
        return _returns_queryset().filter(order_item__seller_order__order__customer=self.request.user.customer)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Через функцию модели: она проверяет срок, статус доставки и количество
        return_request = request_return(request.user.customer, data['order_item'], data['quantity'],
                                        data['reason'], data.get('description', ''))
        return Response(self.get_serializer(self.get_queryset().get(pk=return_request.pk)).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(tags=['Возвраты'], summary='Отменить заявку (пока её не рассмотрели)', request=None,
                   responses=ReturnSerializer)
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return_request = self.get_object()
        return_request.cancel(changed_by=request.user)
        return Response(self.get_serializer(self.get_queryset().get(pk=return_request.pk)).data)


@extend_schema_view(
    list=extend_schema(tags=['Кабинет продавца'], summary='Возвраты по моим товарам'),
    retrieve=extend_schema(tags=['Кабинет продавца'], summary='Возврат по моему товару'),
)
class SellerReturnViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Продавец только смотрит: заявки рассматривает менеджер, товар принимает склад."""
    permission_classes = [IsActiveSeller]
    serializer_class = ReturnSerializer
    filterset_fields = ['status', 'reason']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ReturnRequest.objects.none()
        return _returns_queryset().filter(order_item__seller_order__seller=self.request.user.seller)


class DecisionSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=255, required=False, allow_blank=True,
                                    help_text='Для отказа — обязательно: причину увидит покупатель')


@extend_schema_view(
    list=extend_schema(tags=['Менеджер'], summary='Заявки на возврат (?status=requested — ждут решения)'),
    retrieve=extend_schema(tags=['Менеджер'], summary='Заявка на возврат'),
)
class ManagerReturnViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Менеджер решает по заявке; товар после одобрения принимает склад (/api/warehouse/returns/)."""
    permission_classes = [has_role(User.Role.MANAGER)]
    serializer_class = ReturnSerializer
    filterset_fields = ['status', 'reason']
    ordering = ['created_at']

    def get_queryset(self):
        return _returns_queryset()

    def _decide(self, request, method):
        return_request = self.get_object()
        serializer = DecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if comment := serializer.validated_data.get('comment'):
            return_request.manager_comment = comment
            return_request.save(update_fields=['manager_comment'])
        getattr(return_request, method)(changed_by=request.user)
        return Response(self.get_serializer(self.get_queryset().get(pk=return_request.pk)).data)

    @extend_schema(tags=['Менеджер'], summary='Одобрить возврат', request=DecisionSerializer,
                   responses=ReturnSerializer)
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._decide(request, 'approve')

    @extend_schema(tags=['Менеджер'], summary='Отклонить возврат (с причиной)', request=DecisionSerializer,
                   responses=ReturnSerializer)
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return self._decide(request, 'reject')
