from django.contrib import admin, messages

from .models import Order, OrderError, OrderItem, SellerOrder, StatusHistory


class StatusHistoryInline(admin.TabularInline):
    model = StatusHistory
    extra = 0
    can_delete = False
    fields = ('changed_at', 'seller_order', 'old_status', 'new_status', 'changed_by', 'comment')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class SellerOrderInline(admin.TabularInline):
    model = SellerOrder
    extra = 0
    can_delete = False
    fields = ('seller', 'status', 'subtotal', 'commission', 'seller_payout')
    readonly_fields = fields
    show_change_link = True  # ссылка на страницу подзаказа с позициями

    def has_add_permission(self, request, obj=None):
        return False


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ('product', 'product_name', 'original_price', 'price', 'promotion', 'quantity',
              'calculate_subtotal', 'commission_percent', 'commission', 'seller_payout')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


def _run(modeladmin, request, queryset, method, *args):
    """Вызывает метод модели для каждого выбранного объекта и показывает результат."""
    done = 0
    for obj in queryset:
        try:
            getattr(obj, method)(*args, changed_by=request.user)
            done += 1
        except OrderError as e:
            modeladmin.message_user(request, f'{obj}: {e}', messages.ERROR)
    if done:
        modeladmin.message_user(request, f'Готово: {done}', messages.SUCCESS)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'customer', 'status', 'delivery_type', 'total_amount', 'created_at')
    list_filter = ('status', 'delivery_type', 'created_at')
    search_fields = ('id', 'customer__user__email', 'customer__user__login', 'delivery_address')
    # Статус меняется только действиями — так каждое изменение попадает в историю
    readonly_fields = ('customer', 'status', 'delivery_type', 'pickup_point', 'delivery_address',
                       'total_amount', 'created_at')
    inlines = [SellerOrderInline, StatusHistoryInline]
    actions = ['pay_orders', 'cancel_orders']

    def has_add_permission(self, request):
        return False  # заказы создаются только из корзины

    def has_delete_permission(self, request, obj=None):
        return False  # заказы не удаляются — только отменяются, история сохраняется

    @admin.action(description='Оплатить с баланса покупателя')
    def pay_orders(self, request, queryset):
        _run(self, request, queryset, 'pay')

    @admin.action(description='Отменить заказ целиком')
    def cancel_orders(self, request, queryset):
        _run(self, request, queryset, 'cancel')


def _status_action(status, description):
    def action(modeladmin, request, queryset):
        _run(modeladmin, request, queryset, 'change_status', status)
    action.__name__ = f'set_{status}'
    action.short_description = description
    return action


@admin.register(SellerOrder)
class SellerOrderAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'seller', 'status', 'delivery_status', 'subtotal', 'commission', 'seller_payout', 'updated_at')
    list_filter = ('status', 'seller')
    search_fields = ('order__id', 'seller__store_name')
    readonly_fields = ('order', 'seller', 'status', 'delivery_status', 'subtotal', 'commission', 'seller_payout', 'updated_at')
    inlines = [OrderItemInline, StatusHistoryInline]
    # «Передан в доставку» и «Доставлен» ставит сама доставка (раздел «Доставки»)
    actions = [
        _status_action(SellerOrder.Status.CONFIRMED, 'Подтвердить (продавец)'),
        _status_action(SellerOrder.Status.ASSEMBLING, 'Начать сборку (склад)'),
        _status_action(SellerOrder.Status.READY, 'Собран (склад)'),
        _status_action(SellerOrder.Status.CANCELLED, 'Отменить подзаказ'),
    ]

    @admin.display(description='Доставка')
    def delivery_status(self, obj):
        delivery = getattr(obj, 'delivery', None)
        return delivery.get_status_display() if delivery else '—'

    def has_add_permission(self, request):
        return False
