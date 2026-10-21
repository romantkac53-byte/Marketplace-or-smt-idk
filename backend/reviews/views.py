from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from catalog.models import Product
from marketplace.permissions import IsActiveSeller, IsCustomer, has_role
from users.models import User

from .models import Review, leave_review


class MyReviewSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), source='product')
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Review
        fields = ('id', 'product_id', 'product_name', 'rating', 'text', 'is_published', 'seller_reply',
                  'replied_at', 'created_at', 'updated_at')
        read_only_fields = ('is_published', 'seller_reply', 'replied_at', 'created_at', 'updated_at')


class ReviewUpdateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    text = serializers.CharField(required=False, allow_blank=True)


@extend_schema_view(
    list=extend_schema(tags=['Отзывы'], summary='Мои отзывы'),
    create=extend_schema(tags=['Отзывы'],
                         summary='Оставить отзыв (только на полученный товар; повторно — обновит старый)'),
    partial_update=extend_schema(tags=['Отзывы'], summary='Изменить мой отзыв', request=ReviewUpdateSerializer),
    destroy=extend_schema(tags=['Отзывы'], summary='Удалить мой отзыв'),
)
class MyReviewViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
                      mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsCustomer]
    serializer_class = MyReviewSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Review.objects.none()
        return Review.objects.filter(customer=self.request.user.customer).select_related('product')

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Через функцию модели: она проверяет, что товар куплен и получен
        review = leave_review(request.user.customer, data['product'], data['rating'], data.get('text', ''))
        return Response(self.get_serializer(review).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        review = self.get_object()
        # Чего нет в запросе — берём из текущего отзыва. Значения по одному через .get():
        # данные формы хранятся как «ключ → список», и простое объединение словарей дало бы ['5'] вместо 5
        data = {'rating': review.rating, 'text': review.text}
        data.update({key: request.data.get(key) for key in ('rating', 'text') if key in request.data})
        serializer = ReviewUpdateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        review = leave_review(request.user.customer, review.product, serializer.validated_data['rating'],
                              serializer.validated_data.get('text', ''))
        return Response(self.get_serializer(review).data)


class SellerReviewSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField(source='product.name')
    author = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ('id', 'product_id', 'product_name', 'author', 'rating', 'text', 'is_published', 'seller_reply',
                  'replied_at', 'created_at')

    def get_author(self, review) -> str:
        user = review.customer.user
        return user.public_name


class ReplySerializer(serializers.Serializer):
    text = serializers.CharField()


@extend_schema_view(list=extend_schema(tags=['Кабинет продавца'], summary='Отзывы на мои товары'))
class SellerReviewViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsActiveSeller]
    serializer_class = SellerReviewSerializer
    filterset_fields = ['product', 'rating', 'is_published']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Review.objects.none()
        return Review.objects.filter(product__seller=self.request.user.seller) \
            .select_related('product', 'customer__user')

    @extend_schema(tags=['Кабинет продавца'], summary='Ответить на отзыв', request=ReplySerializer,
                   responses=SellerReviewSerializer)
    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        review = self.get_object()
        serializer = ReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review.reply(serializer.validated_data['text'])
        return Response(self.get_serializer(review).data)


@extend_schema_view(list=extend_schema(tags=['Менеджер'], summary='Все отзывы (модерация)'))
class ManagerReviewViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [has_role(User.Role.MANAGER)]
    serializer_class = SellerReviewSerializer
    queryset = Review.objects.select_related('product', 'customer__user')
    filterset_fields = ['is_published', 'rating', 'product', 'product__seller']
    search_fields = ['text', 'product__name']
    ordering = ['-created_at']

    def _set_published(self, value):
        review = self.get_object()
        review.is_published = value
        review.save(update_fields=['is_published', 'updated_at'])
        return Response(self.get_serializer(review).data)

    @extend_schema(tags=['Менеджер'], summary='Скрыть отзыв (перестаёт влиять на рейтинг)', request=None,
                   responses=SellerReviewSerializer)
    @action(detail=True, methods=['post'])
    def hide(self, request, pk=None):
        return self._set_published(False)

    @extend_schema(tags=['Менеджер'], summary='Опубликовать отзыв', request=None, responses=SellerReviewSerializer)
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        return self._set_published(True)
