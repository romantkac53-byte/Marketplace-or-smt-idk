from django.contrib import admin

from orders.admin import _run

from .models import ReturnHistory, ReturnRequest


class ReturnHistoryInline(admin.TabularInline):
    model = ReturnHistory
    extra = 0
    can_delete = False
    fields = ('changed_at', 'old_status', 'new_status', 'changed_by', 'comment')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'customer', 'seller', 'reason', 'quantity', 'amount', 'status', 'created_at')
    list_filter = ('status', 'reason', 'order_item__seller_order__seller', 'created_at')
    search_fields = ('order_item__product_name', 'order_item__seller_order__order__customer__user__email')
    # Редактируется только комментарий менеджера; статус — действиями, чтобы шла история
    readonly_fields = ('order_item', 'order', 'customer', 'seller', 'quantity', 'amount', 'reason',
                       'description', 'status', 'refund_amount', 'created_at')
    fields = readonly_fields[:-2] + ('manager_comment', 'refund_amount', 'created_at')
    inlines = [ReturnHistoryInline]
    actions = ['approve', 'reject', 'complete']

    def has_add_permission(self, request):
        return False  # заявку подаёт покупатель

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Заказ')
    def order(self, obj):
        return obj.order_item.seller_order.order

    @admin.display(description='Покупатель')
    def customer(self, obj):
        return obj.customer

    @admin.display(description='Продавец')
    def seller(self, obj):
        return obj.order_item.seller_order.seller

    @admin.display(description='Сумма к возврату')
    def amount(self, obj):
        return obj.amount

    @admin.action(description='Одобрить')
    def approve(self, request, queryset):
        _run(self, request, queryset, 'approve')

    @admin.action(description='Отклонить (причина — в комментарии менеджера)')
    def reject(self, request, queryset):
        _run(self, request, queryset, 'reject')

    @admin.action(description='Товар принят на склад — вернуть деньги')
    def complete(self, request, queryset):
        _run(self, request, queryset, 'complete')
