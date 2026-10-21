from decimal import Decimal

from rest_framework import serializers

from catalog.models import Product
from promotions.models import PriceCalculator

from .models import Cart, CartItem


class CartProductSerializer(serializers.ModelSerializer):
    available = serializers.IntegerField(read_only=True)
    seller = serializers.CharField(source='seller.store_name')

    class Meta:
        model = Product
        fields = ('id', 'name', 'image', 'price', 'available', 'seller')


class CartItemSerializer(serializers.ModelSerializer):
    product = CartProductSerializer()
    current_price = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ('id', 'product', 'quantity', 'current_price', 'total_price')

    def _price(self, item):
        _, discount = self.context['price_calculator'].best(item.product)
        return item.product.price - discount

    def get_current_price(self, item) -> str:
        return str(self._price(item))

    def get_total_price(self, item) -> str:
        return str(self._price(item) * item.quantity)


class CartSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ('items', 'items_count', 'total_price')

    def _items(self, cart):
        if '_items' not in self.context:
            self.context.setdefault('price_calculator', PriceCalculator())
            items = cart.items.select_related('product__seller').order_by('added_at')
            self.context['_items'] = CartItemSerializer(items, many=True, context=self.context).data
        return self.context['_items']

    def get_items(self, cart) -> list[dict]:
        return self._items(cart)

    def get_total_price(self, cart) -> str:
        return str(sum((Decimal(i['total_price']) for i in self._items(cart)), Decimal('0')))

    def get_items_count(self, cart) -> int:
        return sum(i['quantity'] for i in self._items(cart))


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), source='product')
    quantity = serializers.IntegerField(min_value=1, default=1)


class SetQuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)
