from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from marketplace.permissions import IsCustomer

from .models import BalanceTransaction
from .serializers import BalanceTransactionSerializer


@extend_schema(tags=['Баланс'], summary='Текущий баланс',
               responses={200: {'type': 'object', 'properties': {'balance': {'type': 'string'}}}})
class BalanceView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        # Пополнение — только через администратора (имитация оплаты), поэтому здесь только просмотр
        return Response({'balance': str(request.user.customer.balance)})


@extend_schema(tags=['Баланс'], summary='История операций: пополнения, оплаты, возвраты')
class BalanceTransactionListView(generics.ListAPIView):
    permission_classes = [IsCustomer]
    serializer_class = BalanceTransactionSerializer
    filterset_fields = ['type']
    ordering = ['-created_at', '-id']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):  # построение документации — пользователя нет
            return BalanceTransaction.objects.none()
        return self.request.user.customer.balance_transactions.all()
