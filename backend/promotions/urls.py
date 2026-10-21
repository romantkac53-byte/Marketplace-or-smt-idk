from rest_framework.routers import DefaultRouter

from . import seller_api

router = DefaultRouter()
router.register('seller/promotions', seller_api.SellerPromotionViewSet, basename='seller-promotion')
router.register('manager/promotions', seller_api.ManagerPromotionViewSet, basename='manager-promotion')

urlpatterns = router.urls
