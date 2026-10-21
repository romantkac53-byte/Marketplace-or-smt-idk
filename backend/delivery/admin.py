from django.contrib import admin, messages

from orders.admin import _run

from .models import Delivery, DeliveryError, DeliveryHistory, PickupPoint


@admin.register(PickupPoint)
class PickupPointAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'address', 'working_hours', 'storage_days', 'is_active')
    list_filter = ('city', 'is_active')
    search_fields = ('name', 'city', 'address')
    list_editable = ('is_active',)
    filter_horizontal = ('employees',)  # удобный выбор сотрудников ПВЗ


class DeliveryHistoryInline(admin.TabularInline):
    model = DeliveryHistory
    extra = 0
    can_delete = False
    fields = ('changed_at', 'old_status', 'new_status', 'changed_by', 'comment')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'delivery_type', 'pickup_point', 'courier', 'status', 'storage_until', 'created_at')
    list_filter = ('status', 'seller_order__order__delivery_type', 'seller_order__order__pickup_point')
    search_fields = ('seller_order__order__id', 'pickup_code', 'courier__email')
    inlines = [DeliveryHistoryInline]
    actions = ['pick_up', 'arrive', 'hand_over', 'return_back', 'return_expired']

    FIELDS = ('seller_order', 'delivery_type', 'pickup_point', 'address', 'courier', 'status',
              'pickup_code', 'storage_until', 'created_at', 'delivered_at')

    def get_fields(self, request, obj=None):
        return self.FIELDS

    def get_readonly_fields(self, request, obj=None):
        # Курьера можно выбрать, пока посылка на складе; остальное меняется только действиями
        if obj and obj.status in (Delivery.Status.PENDING, Delivery.Status.ASSIGNED):
            return [f for f in self.FIELDS if f != 'courier']
        return self.FIELDS

    def has_add_permission(self, request):
        return False  # доставка создаётся сама, когда подзаказ собран

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if 'courier' in form.changed_data and obj.courier:
            courier = obj.courier
            obj.refresh_from_db()  # назначаем через метод, чтобы записалась история
            try:
                obj.assign_courier(courier, changed_by=request.user)
            except DeliveryError as e:
                self.message_user(request, str(e), messages.ERROR)

    @admin.display(description='Способ')
    def delivery_type(self, obj):
        return obj.order.get_delivery_type_display()

    @admin.display(description='Пункт выдачи')
    def pickup_point(self, obj):
        return obj.order.pickup_point or '—'

    @admin.display(description='Адрес')
    def address(self, obj):
        return obj.order.delivery_address

    @admin.action(description='Курьер забрал со склада')
    def pick_up(self, request, queryset):
        _run(self, request, queryset, 'pick_up')

    @admin.action(description='Прибыл в пункт выдачи')
    def arrive(self, request, queryset):
        _run(self, request, queryset, 'arrive_at_pickup_point')

    @admin.action(description='Вручён / выдан покупателю')
    def hand_over(self, request, queryset):
        _run(self, request, queryset, 'hand_over')

    @admin.action(description='Не получен — вернуть на склад')
    def return_back(self, request, queryset):
        _run(self, request, queryset, 'return_to_warehouse')

    @admin.action(description='Вернуть все просроченные в ПВЗ')
    def return_expired(self, request, queryset):
        count = Delivery.return_expired(changed_by=request.user)
        self.message_user(request, f'Возвращено просроченных посылок: {count}')
