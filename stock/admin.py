from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from .models import Stock, StockMovement


class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'current_quantity', 'average_cost', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('product__name', 'product__barcode')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [StockMovementInline]
    actions = ['recalculate_selected_stocks']
    fieldsets = (
        (None, {
            'fields': ('product', 'current_quantity', 'average_cost'),
            'description': _(
                'Podés corregir el stock editando los movimientos abajo: al guardar, '
                'la cantidad y el costo promedio se recalculan solos. '
                'También podés cambiar "Current quantity" directamente si solo querés ajustar el total.'
            ),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.action(description=_('Recalcular stock desde movimientos'))
    def recalculate_selected_stocks(self, request, queryset):
        updated = 0
        for stock in queryset:
            stock.recalculate_from_movements()
            updated += 1
        self.message_user(
            request,
            _('Se recalculó el stock de %(count)s producto(s).') % {'count': updated},
            messages.SUCCESS,
        )


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('id', 'stock', 'type', 'quantity', 'cost_price', 'reason', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('reason', 'stock__product__name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('stock', 'type', 'quantity', 'cost_price', 'reason', 'sale'),
            'description': _(
                'Al guardar o eliminar un movimiento, el stock del producto se actualiza automáticamente.'
            ),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
