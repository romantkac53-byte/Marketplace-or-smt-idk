from django.urls import path

from . import views

urlpatterns = [
    path('reports/dashboard/', views.DashboardView.as_view(), name='report-dashboard'),
    path('reports/sellers/', views.SellersReportView.as_view(), name='report-sellers'),
    path('reports/categories/', views.CategoriesReportView.as_view(), name='report-categories'),
    path('reports/products/', views.ProductsReportView.as_view(), name='report-products'),
    path('seller/stats/', views.SellerStatsView.as_view(), name='seller-stats'),
]
