from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Stock, StockMovement


class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'current_quantity', 'average_cost', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('product__name', 'product__barcode')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [StockMovementInline]
    fieldsets = (
        (None, {
            'fields': ('product', 'current_quantity', 'average_cost')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('id', 'stock', 'type', 'quantity', 'cost_price', 'reason', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('reason', 'stock__product__name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('stock', 'type', 'quantity', 'cost_price', 'reason', 'sale')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
