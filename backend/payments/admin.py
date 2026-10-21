from django import forms
from django.contrib import admin, messages

from .models import BalanceTransaction, Payment, PaymentError, top_up


class TopUpForm(forms.ModelForm):
    class Meta:
        model = BalanceTransaction
        fields = ('customer', 'amount', 'comment')

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('Сумма пополнения должна быть больше нуля')
        return amount


@admin.register(BalanceTransaction)
class BalanceTransactionAdmin(admin.ModelAdmin):
    """Журнал баланса. Через «Добавить» администратор пополняет баланс покупателя."""

    list_display = ('created_at', 'customer', 'type', 'amount', 'balance_after', 'order', 'created_by')
    list_filter = ('type', 'created_at')
    search_fields = ('customer__user__email', 'customer__user__login', 'comment')
    autocomplete_fields = ('customer',)

    def get_fields(self, request, obj=None):
        if obj is None:
            return ('customer', 'amount', 'comment')  # форма пополнения
        return ('created_at', 'customer', 'type', 'amount', 'balance_after', 'order', 'created_by', 'comment')

    def get_readonly_fields(self, request, obj=None):
        # Проведённые операции не редактируются
        return () if obj is None else self.get_fields(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = TopUpForm
        return super().get_form(request, obj, **kwargs)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # Вместо простого сохранения — пополнение через сервис: баланс и запись журнала вместе
        tx = top_up(obj.customer, obj.amount, created_by=request.user, comment=obj.comment)
        # Админка дальше работает с obj (ссылка «добавлено …», журнал действий) — переносим в него запись
        for field in tx._meta.concrete_fields:
            setattr(obj, field.attname, getattr(tx, field.attname))
        self.message_user(request, f'Баланс {obj.customer} пополнен на {tx.amount} ₽, теперь {tx.balance_after} ₽')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'order', 'amount', 'refunded_amount', 'status', 'paid_at')
    list_filter = ('status',)
    search_fields = ('order__id', 'order__customer__user__email')
    readonly_fields = ('order', 'amount', 'refunded_amount', 'status', 'error_message', 'created_at', 'paid_at')
    actions = ['process_payments']

    def has_add_permission(self, request):
        return False  # платёж создаётся вместе с заказом

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Провести оплату с баланса')
    def process_payments(self, request, queryset):
        for payment in queryset:
            try:
                payment.process(changed_by=request.user)
                self.message_user(request, f'{payment}: оплачено {payment.amount} ₽', messages.SUCCESS)
            except PaymentError as e:
                self.message_user(request, f'{payment}: {e}', messages.ERROR)
