from django.contrib import admin

from .models import Promotion


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('name', 'discount_type', 'value', 'starts_at', 'ends_at', 'is_active', 'is_running',
                    'seller', 'scope')
    list_filter = ('is_active', 'discount_type', 'seller')
    search_fields = ('name',)
    list_editable = ('is_active',)
    autocomplete_fields = ('seller', 'products', 'categories')
    fieldsets = (
        (None, {'fields': ('name', 'discount_type', 'value', 'starts_at', 'ends_at', 'is_active')}),
        ('На что действует', {
            'fields': ('seller', 'products', 'categories'),
            'description': 'Ничего не выбрано — на все товары (продавца, если он указан, иначе всей площадки).',
        }),
    )

    @admin.display(description='Действует сейчас', boolean=True)
    def is_running(self, obj):
        return obj.is_running

    @admin.display(description='Область')
    def scope(self, obj):
        parts = []
        if n := obj.products.count():
            parts.append(f'товаров: {n}')
        if n := obj.categories.count():
            parts.append(f'категорий: {n}')
        return ', '.join(parts) or 'все товары'
