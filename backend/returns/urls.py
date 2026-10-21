from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('returns', views.MyReturnViewSet, basename='my-return')
router.register('seller/returns', views.SellerReturnViewSet, basename='seller-return')
router.register('manager/returns', views.ManagerReturnViewSet, basename='manager-return')

urlpatterns = router.urls
