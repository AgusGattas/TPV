from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import ExpenseCategory, FixedExpense, MonthlyExpense, ExpensePayment, VariableExpense


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'color']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': ('name', 'is_active', 'color')
        }),
        (_('Descripción'), {
            'fields': ('description',)
        }),
    )


class MonthlyExpenseInline(admin.TabularInline):
    model = MonthlyExpense
    extra = 0
    readonly_fields = ['paid_amount', 'remaining_amount', 'is_overdue']
    fields = ['year', 'month', 'amount', 'due_date', 'payment_status', 'is_paid']


@admin.register(FixedExpense)
class FixedExpenseAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'amount', 'frequency', 'due_day', 'is_active']
    list_filter = ['category', 'frequency', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    inlines = [MonthlyExpenseInline]
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': ('name', 'category', 'is_active')
        }),
        (_('Configuración de Pago'), {
            'fields': ('amount', 'frequency', 'due_day')
        }),
        (_('Descripción'), {
            'fields': ('description', 'notes')
        }),
        (_('Estadísticas'), {
            'fields': (),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category')


class ExpensePaymentInline(admin.TabularInline):
    model = ExpensePayment
    extra = 0
    readonly_fields = ['created_at']
    fields = ['amount', 'payment_date', 'payment_method', 'reference', 'notes']


@admin.register(MonthlyExpense)
class MonthlyExpenseAdmin(admin.ModelAdmin):
    list_display = ['fixed_expense', 'year', 'month', 'amount', 'due_date', 
                   'payment_status', 'is_paid', 'is_overdue']
    list_filter = ['payment_status', 'is_paid', 'year', 'month', 'due_date', 'fixed_expense__category']
    search_fields = ['fixed_expense__name', 'notes']
    readonly_fields = ['paid_amount', 'remaining_amount', 'is_overdue']
    inlines = [ExpensePaymentInline]
    
    fieldsets = (
        (_('Información del Gasto'), {
            'fields': ('fixed_expense', 'year', 'month', 'amount', 'due_date')
        }),
        (_('Estado de Pago'), {
            'fields': ('payment_status', 'is_paid', 'paid_amount', 'remaining_amount', 'is_overdue')
        }),
        (_('Notas'), {
            'fields': ('notes',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('fixed_expense__category')


@admin.register(ExpensePayment)
class ExpensePaymentAdmin(admin.ModelAdmin):
    list_display = ['monthly_expense', 'amount', 'payment_date', 'payment_method', 'reference']
    list_filter = ['payment_method', 'payment_date', 'monthly_expense__fixed_expense__category']
    search_fields = ['monthly_expense__fixed_expense__name', 'reference']
    readonly_fields = ['created_at']
    
    fieldsets = (
        (_('Información de Pago'), {
            'fields': ('monthly_expense', 'amount', 'payment_date', 'payment_method')
        }),
        (_('Detalles'), {
            'fields': ('reference', 'notes')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'monthly_expense__fixed_expense__category'
        )


@admin.register(VariableExpense)
class VariableExpenseAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'amount', 'expense_date', 'payment_status', 'payment_method']
    list_filter = ['category', 'payment_status', 'payment_method', 'expense_date']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']
    
    fieldsets = (
        (_('Información del Gasto'), {
            'fields': ('name', 'category', 'amount', 'expense_date')
        }),
        (_('Información de Pago'), {
            'fields': ('payment_status', 'payment_method')
        }),
        (_('Descripción'), {
            'fields': ('description', 'notes')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category')
