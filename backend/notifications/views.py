from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'text', 'link', 'is_read', 'created_at')


@extend_schema_view(list=extend_schema(tags=['Уведомления'], summary='Мои уведомления (новые сверху)'))
class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    filterset_fields = ['is_read']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user)  # только свои

    @extend_schema(tags=['Уведомления'], summary='Сколько непрочитанных (для счётчика на колокольчике)',
                   responses={200: {'type': 'object', 'properties': {'unread': {'type': 'integer'}}}})
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        return Response({'unread': self.get_queryset().filter(is_read=False).count()})

    @extend_schema(tags=['Уведомления'], summary='Отметить прочитанным', request=None, responses=NotificationSerializer)
    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(self.get_serializer(notification).data)

    @extend_schema(tags=['Уведомления'], summary='Прочитать все', request=None,
                   responses={200: {'type': 'object', 'properties': {'updated': {'type': 'integer'}}}})
    @action(detail=False, methods=['post'], url_path='read-all')
    def read_all(self, request):
        return Response({'updated': self.get_queryset().filter(is_read=False).update(is_read=True)})
