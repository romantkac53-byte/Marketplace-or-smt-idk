from rest_framework.routers import DefaultRouter

from . import staff_api, views

router = DefaultRouter()
router.register('pickup-points', views.PickupPointViewSet, basename='pickup-point')
router.register('courier/deliveries', staff_api.CourierDeliveryViewSet, basename='courier-delivery')
router.register('pickup/deliveries', staff_api.PickupPointDeliveryViewSet, basename='pickup-delivery')
router.register('manager/deliveries', staff_api.ManagerDeliveryViewSet, basename='manager-delivery')

urlpatterns = router.urls
