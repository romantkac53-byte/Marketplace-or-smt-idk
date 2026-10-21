from django import forms
from django.contrib import admin

from .models import StockMovement, move_stock


class ManualMovementForm(forms.ModelForm):
    """Форма ручной складской операции: приход, списание или инвентаризация."""

    type = forms.ChoiceField(
        label='Операция',
        choices=[(t.value, t.label) for t in StockMovement.MANUAL_TYPES],
        help_text='Для инвентаризации укажите фактический остаток, который насчитали на складе',
    )

    class Meta:
        model = StockMovement
        fields = ('product', 'type', 'quantity', 'comment')

    def clean(self):
        data = super().clean()
        product, type, quantity = data.get('product'), data.get('type'), data.get('quantity')
        if product is None or type is None or quantity is None:
            return data
        if quantity == 0 and type != StockMovement.Type.INVENTORY:
            raise forms.ValidationError('Количество должно быть больше нуля')
        if type == StockMovement.Type.WRITE_OFF and quantity > product.available:
            raise forms.ValidationError(
                f'Списать можно не больше {product.available} шт.: '
                f'остальные {product.reserved} зарезервированы под заказы'
            )
        if type == StockMovement.Type.INVENTORY and quantity < product.reserved:
            raise forms.ValidationError(
                f'Под заказы зарезервировано {product.reserved} шт. — '
                f'фактический остаток не может быть меньше'
            )
        return data


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'product', 'type', 'stock_delta', 'reserved_delta',
                    'stock_after', 'reserved_after', 'seller_order', 'created_by')
    list_filter = ('type', 'created_at', 'product__seller')
    search_fields = ('product__name', 'comment')
    autocomplete_fields = ('product',)

    READ_FIELDS = ('created_at', 'product', 'type', 'quantity', 'stock_delta', 'reserved_delta',
                   'stock_after', 'reserved_after', 'seller_order', 'created_by', 'comment')

    def get_fields(self, request, obj=None):
        return ('product', 'type', 'quantity', 'comment') if obj is None else self.READ_FIELDS

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else self.READ_FIELDS  # проведённые операции не редактируются

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = ManualMovementForm
        return super().get_form(request, obj, **kwargs)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # Проводим через move_stock: остаток товара и запись журнала меняются вместе.
        # Все ошибки уже поймала форма выше; move_stock перепроверит под блокировкой строки товара
        movement = move_stock(obj.product, obj.type, obj.quantity,
                              created_by=request.user, comment=obj.comment)
        # Админка дальше работает с obj (ссылка «добавлено …», журнал действий) — переносим в него запись
        for field in movement._meta.concrete_fields:
            setattr(obj, field.attname, getattr(movement, field.attname))
