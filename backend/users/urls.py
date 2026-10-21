from django.urls import path
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView, TokenRefreshView

from . import staff_api, views
from .serializers import LoginSerializer

# Подписи стандартных эндпоинтов simplejwt для документации
auth = extend_schema_view(post=extend_schema(tags=['Авторизация']))


@auth
class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer  # принимает email или логин



RefreshView = auth(TokenRefreshView)
LogoutView = auth(TokenBlacklistView)

# Персонал: менеджер (продавцы) и администратор (пользователи)
router = DefaultRouter()
router.register('manager/sellers', staff_api.ManagerSellerViewSet, basename='manager-seller')
router.register('admin/users', staff_api.AdminUserViewSet, basename='admin-user')

urlpatterns = [
    path('auth/register/customer/', views.CustomerRegisterView.as_view(), name='register-customer'),
    path('auth/register/seller/', views.SellerRegisterView.as_view(), name='register-seller'),
    path('auth/login/', LoginView.as_view(), name='login'),            # email или логин + пароль → токены
    path('auth/refresh/', RefreshView.as_view(), name='token-refresh'),  # refresh → новый access
    path('auth/logout/', LogoutView.as_view(), name='logout'),          # refresh в чёрный список
    path('me/', views.MeView.as_view(), name='me'),
    path('me/password/', views.PasswordChangeView.as_view(), name='password-change'),
    *router.urls,
]
