from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from marketplace.permissions import IsCustomer

from .models import Cart
from .serializers import AddToCartSerializer, CartSerializer, SetQuantitySerializer


def _cart(request):
    cart, _ = Cart.objects.get_or_create(customer=request.user.customer)
    return cart


def _cart_response(cart, code=status.HTTP_200_OK):
    """Все изменения корзины возвращают её целиком — фронтенду не нужен отдельный запрос."""
    return Response(CartSerializer(cart).data, status=code)


class CartView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(tags=['Корзина'], summary='Моя корзина', responses=CartSerializer)
    def get(self, request):
        return _cart_response(_cart(request))

    @extend_schema(tags=['Корзина'], summary='Очистить корзину', responses=CartSerializer)
    def delete(self, request):
        cart = _cart(request)
        cart.items.all().delete()
        return _cart_response(cart)


class CartItemsView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(tags=['Корзина'], summary='Добавить товар (повторно — увеличит количество)',
                   request=AddToCartSerializer, responses={201: CartSerializer})
    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = _cart(request)
        cart.add_product(serializer.validated_data['product'], serializer.validated_data['quantity'])
        return _cart_response(cart, status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(tags=['Корзина'], summary='Изменить количество', request=SetQuantitySerializer,
                   responses=CartSerializer)
    def patch(self, request, item_id):
        cart = _cart(request)
        item = get_object_or_404(cart.items, pk=item_id)  # только позиции своей корзины
        serializer = SetQuantitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart.set_quantity(item, serializer.validated_data['quantity'])
        return _cart_response(cart)

    @extend_schema(tags=['Корзина'], summary='Убрать товар из корзины', responses=CartSerializer)
    def delete(self, request, item_id):
        cart = _cart(request)
        get_object_or_404(cart.items, pk=item_id).delete()
        return _cart_response(cart)
