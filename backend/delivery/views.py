from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import PickupPoint
from .serializers import PickupPointSerializer


@extend_schema_view(
    list=extend_schema(tags=['Пункты выдачи'], summary='Список работающих пунктов выдачи'),
    retrieve=extend_schema(tags=['Пункты выдачи'], summary='Пункт выдачи'),
)
class PickupPointViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = PickupPointSerializer
    queryset = PickupPoint.objects.filter(is_active=True)
    filterset_fields = ['city']
    search_fields = ['name', 'city', 'address']
    pagination_class = None  # пунктов немного — отдаём сразу все, для карты/выпадающего списка
