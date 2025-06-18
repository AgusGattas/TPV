from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import StockMovement, StockMovementItem


class StockMovementItemInline(admin.TabularInline):
    model = StockMovementItem
    extra = 0


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'type', 'reason', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('reason', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [StockMovementItemInline]
    fieldsets = (
        (None, {
            'fields': ('user', 'type', 'reason')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StockMovementItem)
class StockMovementItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'stock_movement', 'product', 'quantity', 'unit_price')
    list_filter = ('stock_movement__type', 'created_at')
    search_fields = ('product__name', 'stock_movement__reason')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('stock_movement', 'product', 'quantity', 'unit_price')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
