from rest_framework.routers import DefaultRouter

from . import seller_api, views

router = DefaultRouter()
router.register('orders', views.OrderViewSet, basename='order')
router.register('seller/orders', seller_api.SellerOrderViewSet, basename='seller-order')

urlpatterns = router.urls
