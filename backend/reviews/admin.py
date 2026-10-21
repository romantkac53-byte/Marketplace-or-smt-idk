from django.contrib import admin
from django.utils import timezone

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'customer', 'rating', 'short_text', 'is_published', 'has_reply', 'created_at')
    list_filter = ('is_published', 'rating', 'product__seller', 'created_at')
    search_fields = ('product__name', 'customer__user__email', 'customer__user__login', 'text')
    list_editable = ('is_published',)  # модерация прямо из списка
    # Текст и оценку пишет покупатель — в админке их не правят; ответ продавца можно написать
    readonly_fields = ('product', 'customer', 'rating', 'text', 'replied_at', 'created_at', 'updated_at')
    fields = ('product', 'customer', 'rating', 'text', 'is_published', 'seller_reply', 'replied_at',
              'created_at', 'updated_at')
    actions = ['publish', 'hide']

    def has_add_permission(self, request):
        return False  # отзыв оставляет только покупатель, получивший товар

    @admin.display(description='Текст')
    def short_text(self, obj):
        return obj.text[:60] + ('…' if len(obj.text) > 60 else '')

    @admin.display(description='Ответ', boolean=True)
    def has_reply(self, obj):
        return bool(obj.seller_reply)

    def save_model(self, request, obj, form, change):
        if 'seller_reply' in form.changed_data:
            obj.replied_at = timezone.now() if obj.seller_reply else None
        super().save_model(request, obj, form, change)

    @admin.action(description='Опубликовать')
    def publish(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description='Скрыть (модерация)')
    def hide(self, request, queryset):
        queryset.update(is_published=False)
