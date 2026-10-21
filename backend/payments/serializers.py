from rest_framework import serializers

from .models import BalanceTransaction, Payment


class PaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display')

    class Meta:
        model = Payment
        fields = ('amount', 'refunded_amount', 'status', 'status_display', 'error_message', 'paid_at')


class BalanceTransactionSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display')
    order_id = serializers.IntegerField(allow_null=True)

    class Meta:
        model = BalanceTransaction
        fields = ('id', 'type', 'type_display', 'amount', 'balance_after', 'order_id', 'comment', 'created_at')
