from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Customer, Seller, User


class UserCreationFormByEmail(UserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'login')

    def clean(self):
        data = super().clean()
        if not data.get('email') and not data.get('login'):
            raise forms.ValidationError('Укажите email или логин')
        return data


class UserChangeFormByEmail(UserChangeForm):
    class Meta:
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = UserCreationFormByEmail
    form = UserChangeFormByEmail
    list_display = ('email', 'login', 'full_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('email', 'login', 'first_name', 'last_name')
    ordering = ('id',)
    fieldsets = (
        (None, {'fields': ('email', 'login', 'password')}),
        ('Личные данные', {'fields': ('first_name', 'last_name', 'role')}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'login', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'address', 'balance')
    search_fields = ('user__email', 'user__login', 'user__first_name', 'user__last_name', 'phone')
    # Баланс только для просмотра: пополнение — в «Операции по балансу» → «Добавить»
    readonly_fields = ('balance',)


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'user', 'status')
    list_filter = ('status',)
    search_fields = ('store_name', 'user__email', 'user__login')
    list_editable = ('status',)
