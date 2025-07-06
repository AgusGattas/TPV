from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('subtotal', 'total')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'cashbox', 'total_final', 'payment_method', 'created_at')
    list_filter = ('payment_method', 'created_at')
    search_fields = ('user__email', 'id')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [SaleItemInline]
    fieldsets = (
        (None, {
            'fields': ('user', 'cashbox', 'payment_method')
        }),
        (_('Amounts'), {
            'fields': ('subtotal', 'total_discount', 'total_final')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
