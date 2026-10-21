"""Кабинеты курьера и сотрудника ПВЗ, назначение курьеров менеджером."""
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from marketplace.permissions import has_role
from orders.serializers import CommentSerializer
from users.models import User

from .models import Delivery, DeliveryError
from .serializers import DeliveryHistorySerializer

IsCourier = has_role(User.Role.COURIER)
IsPickupStaff = has_role(User.Role.PICKUP)
IsManager = has_role(User.Role.MANAGER)


class StaffDeliverySerializer(serializers.ModelSerializer):
    """Доставка глазами персонала. Кода получения здесь НЕТ — его называет покупатель при вручении."""

    seller_order_id = serializers.IntegerField()
    order_id = serializers.IntegerField(source='seller_order.order_id')
    seller = serializers.CharField(source='seller_order.seller.store_name')
    status_display = serializers.CharField(source='get_status_display')
    delivery_type = serializers.CharField(source='seller_order.order.delivery_type')
    address = serializers.CharField(source='seller_order.order.delivery_address')
    pickup_point = serializers.StringRelatedField(source='seller_order.order.pickup_point')
    recipient = serializers.SerializerMethodField()
    courier = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()
    history = DeliveryHistorySerializer(many=True)

    class Meta:
        model = Delivery
        fields = ('id', 'seller_order_id', 'order_id', 'seller', 'status', 'status_display', 'delivery_type',
                  'address', 'pickup_point', 'recipient', 'courier', 'items_count', 'storage_until',
                  'delivered_at', 'history')

    def get_recipient(self, delivery) -> dict:
        # Курьеру нужны имя и телефон, чтобы связаться с покупателем; email — не нужен
        customer = delivery.seller_order.order.customer
        return {'name': customer.user.full_name, 'phone': customer.phone}

    def get_courier(self, delivery) -> str | None:
        return delivery.courier.full_name if delivery.courier else None

    def get_items_count(self, delivery) -> int:
        return sum(item.quantity for item in delivery.seller_order.items.all())


def _deliveries():
    return Delivery.objects.select_related(
        'courier', 'seller_order__seller', 'seller_order__order__pickup_point',
        'seller_order__order__customer__user',
    ).prefetch_related('history', 'seller_order__items')


class CodeSerializer(serializers.Serializer):
    code = serializers.CharField(min_length=6, max_length=6, help_text='Код получения, который назвал покупатель')


class _DeliveryActionsMixin:
    """Общее: вернуть свежие данные доставки после действия."""

    def _fresh(self, delivery):
        return Response(StaffDeliverySerializer(_deliveries().get(pk=delivery.pk)).data)


# ---------- Курьер ----------

@extend_schema_view(
    list=extend_schema(tags=['Курьер'], summary='Мои доставки (по умолчанию — активные)'),
    retrieve=extend_schema(tags=['Курьер'], summary='Доставка'),
)
class CourierDeliveryViewSet(_DeliveryActionsMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                             viewsets.GenericViewSet):
    permission_classes = [IsCourier]
    serializer_class = StaffDeliverySerializer
    filterset_fields = ['status']
    ordering = ['created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Delivery.objects.none()
        qs = _deliveries()
        if self.action == 'available' or self.action == 'take':
            return qs.filter(status=Delivery.Status.PENDING, courier__isnull=True)
        qs = qs.filter(courier=self.request.user)  # изоляция: только свои доставки
        if self.action == 'list' and 'status' not in self.request.query_params:
            qs = qs.filter(status__in=[Delivery.Status.ASSIGNED, Delivery.Status.IN_TRANSIT])
        return qs

    @extend_schema(tags=['Курьер'], summary='Свободные посылки на складе — можно взять себе',
                   responses=StaffDeliverySerializer(many=True))
    @action(detail=False, methods=['get'])
    def available(self, request):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(tags=['Курьер'], summary='Взять посылку себе', request=None, responses=StaffDeliverySerializer)
    @action(detail=True, methods=['post'])
    def take(self, request, pk=None):
        self.get_object()  # 404, если посылки нет среди свободных
        with transaction.atomic():
            # Блокируем строку и перепроверяем: два курьера могли нажать «Взять» одновременно
            delivery = Delivery.objects.select_for_update().get(pk=pk)
            if delivery.courier_id is not None:
                raise DeliveryError('Эту посылку уже взял другой курьер')
            delivery.assign_courier(request.user, changed_by=request.user)
        return self._fresh(delivery)

    @extend_schema(tags=['Курьер'], summary='Забрал со склада — посылка в пути', request=None,
                   responses=StaffDeliverySerializer)
    @action(detail=True, methods=['post'], url_path='pick-up')
    def pick_up(self, request, pk=None):
        delivery = self.get_object()
        delivery.pick_up(changed_by=request.user)
        return self._fresh(delivery)

    @extend_schema(tags=['Курьер'], summary='Вручить покупателю по коду (только курьерская доставка)',
                   request=CodeSerializer, responses=StaffDeliverySerializer)
    @action(detail=True, methods=['post'], url_path='hand-over')
    def hand_over(self, request, pk=None):
        delivery = self.get_object()
        if delivery.is_pickup:
            raise DeliveryError('Эта посылка едет в пункт выдачи — её принимает сотрудник ПВЗ')
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delivery.hand_over(code=serializer.validated_data['code'], changed_by=request.user)
        return self._fresh(delivery)

    @extend_schema(tags=['Курьер'], summary='Не удалось вручить — посылка возвращается на склад, деньги покупателю',
                   request=CommentSerializer, responses=StaffDeliverySerializer)
    @action(detail=True, methods=['post'])
    def fail(self, request, pk=None):
        delivery = self.get_object()
        if delivery.is_pickup:
            raise DeliveryError('Посылку в пункт выдачи нельзя «не вручить» — отвезите её в пункт')
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delivery.return_to_warehouse(changed_by=request.user, comment=serializer.validated_data.get('comment', ''))
        return self._fresh(delivery)


# ---------- Сотрудник ПВЗ ----------

@extend_schema_view(
    list=extend_schema(
        tags=['Пункт выдачи'], summary='Посылки моих пунктов (едут к нам и хранятся у нас)',
        parameters=[OpenApiParameter('code', str, description='Поиск посылки по коду получения')],
    ),
    retrieve=extend_schema(tags=['Пункт выдачи'], summary='Посылка'),
)
class PickupPointDeliveryViewSet(_DeliveryActionsMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                                 viewsets.GenericViewSet):
    permission_classes = [IsPickupStaff]
    serializer_class = StaffDeliverySerializer
    filterset_fields = ['status']
    ordering = ['created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Delivery.objects.none()
        # Изоляция: только посылки в пункты, где работает этот сотрудник
        qs = _deliveries().filter(seller_order__order__pickup_point__in=self.request.user.pickup_points.all())
        if self.action == 'list':
            if code := self.request.query_params.get('code'):
                return qs.filter(pickup_code=code, status=Delivery.Status.AT_PICKUP_POINT)
            if 'status' not in self.request.query_params:
                qs = qs.filter(status__in=[Delivery.Status.IN_TRANSIT, Delivery.Status.AT_PICKUP_POINT])
        return qs

    @extend_schema(tags=['Пункт выдачи'], summary='Посылка прибыла в пункт — начинается срок хранения',
                   request=None, responses=StaffDeliverySerializer)
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        delivery = self.get_object()
        delivery.arrive_at_pickup_point(changed_by=request.user)
        return self._fresh(delivery)

    @extend_schema(tags=['Пункт выдачи'], summary='Выдать покупателю по коду', request=CodeSerializer,
                   responses=StaffDeliverySerializer)
    @action(detail=True, methods=['post'])
    def issue(self, request, pk=None):
        delivery = self.get_object()
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delivery.hand_over(code=serializer.validated_data['code'], changed_by=request.user)
        return self._fresh(delivery)

    @extend_schema(tags=['Пункт выдачи'], summary='Вернуть на склад посылки с истёкшим сроком хранения',
                   request=None, responses={200: {'type': 'object', 'properties': {'returned': {'type': 'integer'}}}})
    @action(detail=False, methods=['post'], url_path='return-expired')
    def return_expired(self, request):
        expired = self.get_queryset().filter(status=Delivery.Status.AT_PICKUP_POINT,
                                             storage_until__lt=timezone.now())
        count = 0
        for delivery in expired:
            delivery.return_to_warehouse(changed_by=request.user, comment='Истёк срок хранения в пункте выдачи')
            count += 1
        return Response({'returned': count})


# ---------- Менеджер: все доставки и назначение курьеров ----------

class AssignCourierSerializer(serializers.Serializer):
    courier_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.COURIER,
                                                                                is_active=True))


@extend_schema_view(
    list=extend_schema(tags=['Менеджер'], summary='Все доставки'),
    retrieve=extend_schema(tags=['Менеджер'], summary='Доставка'),
)
class ManagerDeliveryViewSet(_DeliveryActionsMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                             viewsets.GenericViewSet):
    permission_classes = [IsManager]
    serializer_class = StaffDeliverySerializer
    filterset_fields = ['status', 'courier']
    ordering = ['created_at']
    queryset = _deliveries()

    @extend_schema(tags=['Менеджер'], summary='Назначить или сменить курьера (пока посылка на складе)',
                   request=AssignCourierSerializer, responses=StaffDeliverySerializer)
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        delivery = self.get_object()
        serializer = AssignCourierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delivery.assign_courier(serializer.validated_data['courier_id'], changed_by=request.user)
        return self._fresh(delivery)

    @extend_schema(tags=['Менеджер'], summary='Список курьеров',
                   responses={200: {'type': 'array', 'items': {'type': 'object'}}})
    @action(detail=False, methods=['get'])
    def couriers(self, request):
        couriers = User.objects.filter(role=User.Role.COURIER, is_active=True).order_by('first_name')
        return Response([{'id': c.pk, 'name': c.full_name,
                          'active_deliveries': c.deliveries.filter(
                              status__in=[Delivery.Status.ASSIGNED, Delivery.Status.IN_TRANSIT]).count()}
                         for c in couriers])
