from django.urls import path
from rest_framework.routers import DefaultRouter

from . import favorites_api, seller_api, views

router = DefaultRouter()
router.register('products', views.ProductViewSet, basename='product')
router.register('characteristics', seller_api.CharacteristicViewSet, basename='characteristic')
router.register('seller/products', seller_api.SellerProductViewSet, basename='seller-product')

urlpatterns = [
    path('categories/', views.CategoryTreeView.as_view(), name='category-tree'),
    path('favorites/', favorites_api.FavoritesView.as_view(), name='favorites'),
    path('favorites/ids/', favorites_api.FavoriteIdsView.as_view(), name='favorite-ids'),
    path('favorites/<int:product_id>/', favorites_api.FavoriteDeleteView.as_view(), name='favorite-delete'),
    path('seller/stock-movements/', seller_api.SellerStockMovementListView.as_view(), name='seller-stock'),
    *router.urls,
]
