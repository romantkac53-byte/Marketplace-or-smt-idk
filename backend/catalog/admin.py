from django import forms
from django.contrib import admin

from warehouse.models import StockMovement

from .models import Category, Characteristic, Product, ProductCharacteristic, ProductImage


class SubcategoryInline(admin.TabularInline):
    model = Category
    fk_name = 'parent'
    extra = 0
    fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    verbose_name = 'Подкатегория'
    verbose_name_plural = 'Подкатегории'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'slug', 'parent', 'commission_percent', 'effective_commission')
    list_filter = ('parent',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    inlines = [SubcategoryInline]

    @admin.display(description='Действующая комиссия, %')
    def effective_commission(self, obj):
        return obj.get_commission_percent()  # с учётом наследования от родителя и общего процента


@admin.register(Characteristic)
class CharacteristicAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit')
    search_fields = ('name',)


class ProductCharacteristicInline(admin.TabularInline):
    model = ProductCharacteristic
    extra = 1
    autocomplete_fields = ('characteristic',)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ('image', 'position')
    verbose_name_plural = 'Дополнительные фото (галерея)'


class StockMovementInline(admin.TabularInline):
    """Последние движения товара — только для просмотра."""
    model = StockMovement
    extra = 0
    can_delete = False
    fields = ('created_at', 'type', 'stock_delta', 'reserved_delta', 'stock_after',
              'reserved_after', 'seller_order', 'created_by', 'comment')
    readonly_fields = fields
    ordering = ('-created_at', '-pk')
    verbose_name_plural = 'Движение товара (приход, списание — в разделе «Склад → Движение товаров»)'

    def has_add_permission(self, request, obj=None):
        return False


class ProductAddForm(forms.ModelForm):
    initial_stock = forms.IntegerField(
        label='Начальный остаток', min_value=0, initial=0, required=False,
        help_text='Будет проведён как приход на склад',
    )

    class Meta:
        model = Product
        fields = '__all__'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'article', 'seller', 'category', 'price', 'current_price', 'stock', 'reserved', 'available',
                    'is_active')
    list_filter = ('is_active', 'category', 'seller')
    search_fields = ('name', 'description')
    # Остаток здесь не редактируется — только через журнал склада
    list_editable = ('price', 'is_active')
    readonly_fields = ('article', 'current_price', 'active_promotion', 'stock', 'reserved', 'available')
    inlines = [ProductCharacteristicInline, ProductImageInline, StockMovementInline]

    @admin.display(description='Доступно')
    def available(self, obj):
        return obj.available

    @admin.display(description='Цена со скидкой')
    def current_price(self, obj):
        return obj.current_price

    @admin.display(description='Действующая акция')
    def active_promotion(self, obj):
        return obj.active_promotion or '—'

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = ProductAddForm
        return super().get_form(request, obj, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else self.readonly_fields

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        initial = form.cleaned_data.get('initial_stock') if not change else None
        if initial:
            obj.update_stock(initial, created_by=request.user, comment='Начальный остаток')
