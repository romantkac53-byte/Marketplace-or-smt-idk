from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (CustomerRegisterSerializer, MeSerializer, PasswordChangeSerializer,
                          SellerRegisterSerializer)


@extend_schema(tags=['Авторизация'], summary='Регистрация покупателя')
class CustomerRegisterView(generics.CreateAPIView):
    serializer_class = CustomerRegisterSerializer
    permission_classes = [AllowAny]


@extend_schema(tags=['Авторизация'], summary='Регистрация продавца (магазин будет «На проверке»)')
class SellerRegisterView(generics.CreateAPIView):
    serializer_class = SellerRegisterSerializer
    permission_classes = [AllowAny]


@extend_schema(tags=['Личный кабинет'], summary='Мой профиль')
class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer
    http_method_names = ['get', 'patch']  # PUT не нужен — профиль меняется частично

    def get_object(self):
        return self.request.user


@extend_schema(tags=['Личный кабинет'], summary='Смена пароля', request=PasswordChangeSerializer,
               responses={204: None})
class PasswordChangeView(APIView):
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])
        return Response(status=status.HTTP_204_NO_CONTENT)
