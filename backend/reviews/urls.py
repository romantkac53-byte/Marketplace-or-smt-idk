from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('reviews', views.MyReviewViewSet, basename='my-review')
router.register('seller/reviews', views.SellerReviewViewSet, basename='seller-review')
router.register('manager/reviews', views.ManagerReviewViewSet, basename='manager-review')

urlpatterns = router.urls
