from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Supplier, SupplierInvoice, SupplierPayment


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'cuit', 'email', 'phone', 'is_active', 'total_pending_amount']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'cuit', 'email', 'contact_person']
    readonly_fields = ['total_pending_amount', 'total_paid_amount']
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': ('name', 'cuit', 'is_active')
        }),
        (_('Contacto'), {
            'fields': ('email', 'phone', 'contact_person', 'address')
        }),
        (_('Información Adicional'), {
            'fields': ('notes',)
        }),
        (_('Estadísticas'), {
            'fields': ('total_pending_amount', 'total_paid_amount'),
            'classes': ('collapse',)
        }),
    )


class SupplierPaymentInline(admin.TabularInline):
    model = SupplierPayment
    extra = 0
    readonly_fields = ['created_at']
    fields = ['amount', 'payment_date', 'payment_method', 'reference', 'notes']


@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(admin.ModelAdmin):
    list_display = ['supplier', 'invoice_number', 'invoice_date', 'due_date', 
                   'total_amount', 'payment_status', 'is_paid', 'is_overdue']
    list_filter = ['payment_status', 'is_paid', 'invoice_date', 'due_date', 'supplier']
    search_fields = ['supplier__name', 'invoice_number', 'description']
    readonly_fields = ['paid_amount', 'remaining_amount', 'is_overdue']
    inlines = [SupplierPaymentInline]
    
    fieldsets = (
        (_('Información de Factura'), {
            'fields': ('supplier', 'invoice_number', 'invoice_date', 'due_date', 'total_amount')
        }),
        (_('Detalles'), {
            'fields': ('description', 'notes')
        }),
        (_('Estado de Pago'), {
            'fields': ('payment_status', 'is_paid', 'paid_amount', 'remaining_amount', 'is_overdue')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('supplier')


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'amount', 'payment_date', 'payment_method', 'reference']
    list_filter = ['payment_method', 'payment_date', 'invoice__supplier']
    search_fields = ['invoice__supplier__name', 'invoice__invoice_number', 'reference']
    readonly_fields = ['created_at']
    
    fieldsets = (
        (_('Información de Pago'), {
            'fields': ('invoice', 'amount', 'payment_date', 'payment_method')
        }),
        (_('Detalles'), {
            'fields': ('reference', 'notes')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('invoice__supplier')
