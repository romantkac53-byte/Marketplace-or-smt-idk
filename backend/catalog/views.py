import django_filters
from django.db.models import Avg, Count, F, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import OrderItem, SellerOrder
from promotions.models import PriceCalculator

from .filters import ArticleSearchFilter
from .models import Category, Product
from .serializers import (CategoryTreeSerializer, ProductDetailSerializer, ProductListSerializer,
                          PublicReviewSerializer)


@extend_schema(tags=['Каталог'], summary='Дерево категорий', responses=CategoryTreeSerializer(many=True))
class CategoryTreeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Все категории одним запросом, дерево собираем в памяти
        nodes = {c.id: {'id': c.id, 'name': c.name, 'slug': c.slug, 'children': []}
                 for c in Category.objects.order_by('name')}
        roots = []
        for c in Category.objects.only('id', 'parent_id'):
            (nodes[c.parent_id]['children'] if c.parent_id else roots).append(nodes[c.id])
        roots.sort(key=lambda n: n['name'])
        return Response(roots)


def visible_products():
    """Товары, которые видят покупатели: в продаже и у одобренного магазина."""
    return Product.objects.filter(is_active=True, seller__status='active')


def with_stats(qs):
    """Рейтинг, число отзывов и продаж — для карточек товара и сортировок (каталог и избранное)."""
    # Сколько штук продано (не считая отменённых подзаказов) — для сортировки «популярные»
    sold = OrderItem.objects.filter(product=OuterRef('pk')) \
        .exclude(seller_order__status=SellerOrder.Status.CANCELLED) \
        .values('product').annotate(total=Sum('quantity')).values('total')
    published = Q(reviews__is_published=True)
    return qs.select_related('seller', 'category__parent').annotate(
        rating_avg=Avg('reviews__rating', filter=published),
        reviews_count=Count('reviews', filter=published),
        sold_count=Coalesce(Subquery(sold, output_field=IntegerField()), 0),
    )


class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    """?ids=3,8,15 — список номеров через запятую"""


class ProductFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(method='filter_category', label='Категория (вместе с подкатегориями)')
    seller = django_filters.NumberFilter(field_name='seller_id', label='Продавец')
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte', label='Цена от')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte', label='Цена до')
    in_stock = django_filters.BooleanFilter(method='filter_in_stock', label='Только в наличии')
    ids = NumberInFilter(field_name='id', label='Только эти товары: ?ids=3,8,15 (для «Вы недавно смотрели»)')

    class Meta:
        model = Product
        fields = ['category', 'seller', 'price_min', 'price_max', 'in_stock', 'ids']

    def filter_category(self, queryset, name, value):
        category = Category.objects.filter(pk=value).first()
        if category is None:
            return queryset.none()
        ids = [category.pk] + [c.pk for c in category.get_descendants()]  # «Лекарства» → и «Спреи» тоже
        return queryset.filter(category_id__in=ids)

    def filter_in_stock(self, queryset, name, value):
        return queryset.filter(stock__gt=F('reserved')) if value else queryset


@extend_schema_view(
    list=extend_schema(
        tags=['Каталог'], summary='Список товаров: поиск, фильтры, сортировка',
        parameters=[
            OpenApiParameter('search', OpenApiTypes.STR,
                             description='Текст или артикул: ID123456789 (также «id 123456789», «арт. 123456789», 9 цифр)'),
            OpenApiParameter('char', OpenApiTypes.STR, many=True,
                             description='Фильтр по характеристике «id:значение», например 3:20 мл. Можно несколько.'),
            OpenApiParameter('ordering', OpenApiTypes.STR,
                             description='price, -price, created_at, -created_at, rating_avg, -rating_avg, '
                                         'sold_count, -sold_count, name'),
        ],
    ),
    retrieve=extend_schema(tags=['Каталог'], summary='Страница товара'),
)
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, ArticleSearchFilter, OrderingFilter]  # ?search=ID123456789 — по артикулу
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'category__name', 'seller__store_name']
    ordering_fields = ['price', 'created_at', 'rating_avg', 'sold_count', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = visible_products()
        # Фильтр по характеристикам: ?char=3:20 мл&char=5:Россия (до подсчёта рейтинга, чтобы не исказить Count)
        for item in self.request.query_params.getlist('char'):
            char_id, _, value = item.partition(':')
            if char_id.isdigit() and value:
                qs = qs.filter(characteristics__characteristic_id=char_id, characteristics__value__iexact=value)
        qs = with_stats(qs)
        if self.action == 'retrieve':
            qs = qs.prefetch_related('characteristics__characteristic', 'gallery')
        return qs

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == 'retrieve' else ProductListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['price_calculator'] = PriceCalculator()  # акции загружаются один раз на запрос
        return context

    @extend_schema(tags=['Каталог'], summary='Отзывы о товаре', responses=PublicReviewSerializer(many=True))
    @action(detail=True, methods=['get'], filter_backends=[])
    def reviews(self, request, pk=None):
        product = self.get_object()
        reviews = product.reviews.filter(is_published=True).select_related('customer__user')
        page = self.paginate_queryset(reviews)
        return self.get_paginated_response(PublicReviewSerializer(page, many=True).data)
