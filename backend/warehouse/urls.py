from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api

router = DefaultRouter()
router.register('warehouse/assembly', api.AssemblyViewSet, basename='warehouse-assembly')
router.register('warehouse/returns', api.WarehouseReturnViewSet, basename='warehouse-return')

urlpatterns = [
    path('warehouse/stock/', api.StockLevelListView.as_view(), name='warehouse-stock'),
    path('warehouse/movements/', api.StockMovementListCreateView.as_view(), name='warehouse-movements'),
    *router.urls,
]
