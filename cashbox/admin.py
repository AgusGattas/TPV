from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import CashBox, CashMovement


class CashMovementInline(admin.TabularInline):
    model = CashMovement
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CashBox)
class CashBoxAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'opened_at', 'closed_at', 'initial_cash', 'calculated_cash', 'difference')
    list_filter = ('opened_at', 'closed_at')
    search_fields = ('user__email', 'id')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CashMovementInline]
    fieldsets = (
        (None, {
            'fields': ('user', 'opened_at', 'initial_cash')
        }),
        (_('Closing Information'), {
            'fields': ('closed_at', 'calculated_cash', 'counted_cash', 'difference', 'cash_to_keep', 'cash_to_withdraw')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = ('id', 'cashbox', 'user', 'type', 'amount', 'reason', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('reason', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('cashbox', 'user', 'type', 'amount', 'reason')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
