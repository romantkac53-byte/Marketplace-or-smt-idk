"""Избранное покупателя: ♡ на карточках товара и страница «Избранное»."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from marketplace.permissions import IsCustomer
from promotions.models import PriceCalculator

from .models import Favorite, Product
from .serializers import ProductListSerializer
from .views import visible_products, with_stats


class FavoriteAddSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))


class FavoritesView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(tags=['Избранное'], summary='Мои избранные товары (снятые с продажи не показываются)',
                   responses=ProductListSerializer(many=True))
    def get(self, request):
        products = with_stats(visible_products().filter(favorited_by__customer=request.user.customer)) \
            .order_by('-favorited_by__created_at')
        context = {'request': request, 'price_calculator': PriceCalculator()}
        return Response(ProductListSerializer(products, many=True, context=context).data)

    @extend_schema(tags=['Избранное'], summary='Добавить в избранное (повторно — ничего не изменится)',
                   request=FavoriteAddSerializer, responses={201: None})
    def post(self, request):
        serializer = FavoriteAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        Favorite.objects.get_or_create(customer=request.user.customer, product=serializer.validated_data['product_id'])
        return Response(status=status.HTTP_201_CREATED)


class FavoriteIdsView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(tags=['Избранное'], summary='Номера избранных товаров — чтобы закрасить ♡ на карточках',
                   responses={200: {'type': 'array', 'items': {'type': 'integer'}}})
    def get(self, request):
        return Response(list(request.user.customer.favorites.values_list('product_id', flat=True)))


class FavoriteDeleteView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(tags=['Избранное'], summary='Убрать из избранного', responses={204: None})
    def delete(self, request, product_id):
        get_object_or_404(request.user.customer.favorites, product_id=product_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
