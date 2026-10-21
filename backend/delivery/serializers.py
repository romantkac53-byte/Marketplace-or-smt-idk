from rest_framework import serializers

from .models import Delivery, DeliveryHistory, PickupPoint


class PickupPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickupPoint
        fields = ('id', 'name', 'city', 'address', 'working_hours', 'storage_days')


class DeliveryHistorySerializer(serializers.ModelSerializer):
    status = serializers.CharField(source='new_status')
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryHistory
        fields = ('status', 'status_display', 'changed_at', 'comment')

    def get_status_display(self, entry) -> str:
        return Delivery.Status(entry.new_status).label


class CustomerDeliverySerializer(serializers.ModelSerializer):
    """Отслеживание доставки покупателем (use case «Отслеживание доставки»)."""

    status_display = serializers.CharField(source='get_status_display')
    courier = serializers.SerializerMethodField()
    history = DeliveryHistorySerializer(many=True)

    class Meta:
        model = Delivery
        fields = ('status', 'status_display', 'courier', 'pickup_code', 'storage_until', 'delivered_at', 'history')

    def get_courier(self, delivery) -> str | None:
        # Покупателю — только имя курьера, без email
        return (delivery.courier.first_name or 'Курьер') if delivery.courier else None
