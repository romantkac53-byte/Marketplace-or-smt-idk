from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'text', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__email', 'user__login', 'text')
