from django.urls import path

from . import views

urlpatterns = [
    path('balance/', views.BalanceView.as_view(), name='balance'),
    path('balance/transactions/', views.BalanceTransactionListView.as_view(), name='balance-transactions'),
]
