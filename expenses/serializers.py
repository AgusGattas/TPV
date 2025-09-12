from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import ExpenseCategory, FixedExpense, MonthlyExpense, ExpensePayment, VariableExpense


class ExpenseCategorySerializer(serializers.ModelSerializer):
    expenses_count = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseCategory
        fields = [
            'id', 'name', 'description', 'is_active', 'color', 
            'created_at', 'expenses_count'
        ]

    def get_expenses_count(self, obj):
        return obj.expenses.count()


class FixedExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    monthly_amount = serializers.SerializerMethodField()
    monthly_expenses_count = serializers.SerializerMethodField()

    class Meta:
        model = FixedExpense
        fields = [
            'id', 'name', 'category', 'category_name', 'amount', 'frequency',
            'due_day', 'description', 'is_active', 'notes', 'created_at',
            'monthly_amount', 'monthly_expenses_count'
        ]

    def get_monthly_amount(self, obj):
        return obj.monthly_amount

    def get_monthly_expenses_count(self, obj):
        return obj.monthly_expenses.count()


class MonthlyExpenseSerializer(serializers.ModelSerializer):
    fixed_expense_name = serializers.CharField(source='fixed_expense.name', read_only=True)
    category_name = serializers.CharField(source='fixed_expense.category.name', read_only=True)
    paid_amount = serializers.ReadOnlyField()
    remaining_amount = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    payments_count = serializers.SerializerMethodField()

    class Meta:
        model = MonthlyExpense
        fields = [
            'id', 'fixed_expense', 'fixed_expense_name', 'category_name',
            'year', 'month', 'amount', 'due_date', 'payment_status',
            'is_paid', 'notes', 'created_at', 'paid_amount', 
            'remaining_amount', 'is_overdue', 'payments_count'
        ]

    def get_payments_count(self, obj):
        return obj.payments.count()


class ExpensePaymentSerializer(serializers.ModelSerializer):
    monthly_expense_name = serializers.CharField(source='monthly_expense.fixed_expense.name', read_only=True)
    category_name = serializers.CharField(source='monthly_expense.fixed_expense.category.name', read_only=True)

    class Meta:
        model = ExpensePayment
        fields = [
            'id', 'monthly_expense', 'monthly_expense_name', 'category_name',
            'amount', 'payment_date', 'payment_method', 'reference', 
            'notes', 'created_at'
        ]

    def validate(self, data):
        monthly_expense = data.get('monthly_expense')
        amount = data.get('amount')
        
        if monthly_expense and amount:
            # Verificar que el monto no exceda lo que falta pagar
            remaining = monthly_expense.remaining_amount
            if amount > remaining:
                raise serializers.ValidationError(
                    _("El monto del pago no puede exceder el monto restante por pagar")
                )
        
        return data


class VariableExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = VariableExpense
        fields = [
            'id', 'name', 'category', 'category_name', 'amount', 'expense_date',
            'payment_status', 'payment_method', 'description', 'notes', 'created_at'
        ]


class MonthlyExpenseDetailSerializer(MonthlyExpenseSerializer):
    payments = ExpensePaymentSerializer(many=True, read_only=True)

    class Meta(MonthlyExpenseSerializer.Meta):
        fields = MonthlyExpenseSerializer.Meta.fields + ['payments']


class FixedExpenseDetailSerializer(FixedExpenseSerializer):
    monthly_expenses = MonthlyExpenseSerializer(many=True, read_only=True)

    class Meta(FixedExpenseSerializer.Meta):
        fields = FixedExpenseSerializer.Meta.fields + ['monthly_expenses']


class ExpenseCategoryDetailSerializer(ExpenseCategorySerializer):
    expenses = FixedExpenseSerializer(many=True, read_only=True)
    variable_expenses = VariableExpenseSerializer(many=True, read_only=True)

    class Meta(ExpenseCategorySerializer.Meta):
        fields = ExpenseCategorySerializer.Meta.fields + ['expenses', 'variable_expenses'] 