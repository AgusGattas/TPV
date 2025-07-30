from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
import calendar

from django_base.base_utils.base_viewsets import BaseModelViewSet
from .models import ExpenseCategory, FixedExpense, MonthlyExpense, ExpensePayment, VariableExpense
from .serializers import (
    ExpenseCategorySerializer, ExpenseCategoryDetailSerializer,
    FixedExpenseSerializer, FixedExpenseDetailSerializer,
    MonthlyExpenseSerializer, MonthlyExpenseDetailSerializer,
    ExpensePaymentSerializer, VariableExpenseSerializer
)


class ExpenseCategoryViewSet(BaseModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    
    serializers = {
        "retrieve": ExpenseCategoryDetailSerializer,
        "list": ExpenseCategorySerializer,
        "default": ExpenseCategorySerializer,
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Búsqueda por nombre
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Estadísticas generales de categorías"""
        total_categories = ExpenseCategory.objects.filter(is_active=True).count()
        total_fixed_expenses = FixedExpense.objects.filter(is_active=True).count()
        total_variable_expenses = VariableExpense.objects.count()
        
        return Response({
            'total_categories': total_categories,
            'total_fixed_expenses': total_fixed_expenses,
            'total_variable_expenses': total_variable_expenses,
        })


class FixedExpenseViewSet(BaseModelViewSet):
    queryset = FixedExpense.objects.all()
    serializer_class = FixedExpenseSerializer
    
    serializers = {
        "retrieve": FixedExpenseDetailSerializer,
        "list": FixedExpenseSerializer,
        "default": FixedExpenseSerializer,
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        frequency = self.request.query_params.get('frequency')
        if frequency:
            queryset = queryset.filter(frequency=frequency)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Búsqueda por nombre
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Estadísticas de gastos fijos"""
        total_expenses = FixedExpense.objects.filter(is_active=True).count()
        total_monthly_amount = sum(
            expense.get_monthly_amount() 
            for expense in FixedExpense.objects.filter(is_active=True)
        )
        
        # Gastos por categoría
        expenses_by_category = FixedExpense.objects.filter(is_active=True).values(
            'category__name'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        return Response({
            'total_expenses': total_expenses,
            'total_monthly_amount': total_monthly_amount,
            'expenses_by_category': expenses_by_category,
        })


class MonthlyExpenseViewSet(BaseModelViewSet):
    queryset = MonthlyExpense.objects.all()
    serializer_class = MonthlyExpenseSerializer
    
    serializers = {
        "retrieve": MonthlyExpenseDetailSerializer,
        "list": MonthlyExpenseSerializer,
        "default": MonthlyExpenseSerializer,
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
        fixed_expense_id = self.request.query_params.get('fixed_expense')
        if fixed_expense_id:
            queryset = queryset.filter(fixed_expense_id=fixed_expense_id)
        
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(fixed_expense__category_id=category_id)
        
        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        is_paid = self.request.query_params.get('is_paid')
        if is_paid is not None:
            queryset = queryset.filter(is_paid=is_paid.lower() == 'true')
        
        # Filtro por año y mes
        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(year=year)
        
        month = self.request.query_params.get('month')
        if month:
            queryset = queryset.filter(month=month)
        
        # Filtro por rango de fechas
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(due_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(due_date__lte=end_date)
        
        return queryset

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Gastos vencidos"""
        overdue_expenses = self.get_queryset().filter(
            due_date__lt=timezone.now().date(),
            is_paid=False
        )
        serializer = self.get_serializer(overdue_expenses, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Estadísticas de gastos mensuales"""
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        queryset = self.get_queryset()
        
        if start_date:
            queryset = queryset.filter(due_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(due_date__lte=end_date)
        
        total_expenses = queryset.count()
        total_amount = queryset.aggregate(total=Sum('amount'))['total'] or 0
        paid_amount = queryset.filter(is_paid=True).aggregate(total=Sum('amount'))['total'] or 0
        pending_amount = total_amount - paid_amount
        
        # Gastos por categoría
        expenses_by_category = queryset.values('fixed_expense__category__name').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        return Response({
            'total_expenses': total_expenses,
            'total_amount': total_amount,
            'paid_amount': paid_amount,
            'pending_amount': pending_amount,
            'expenses_by_category': expenses_by_category,
        })


class ExpensePaymentViewSet(BaseModelViewSet):
    queryset = ExpensePayment.objects.all()
    serializer_class = ExpensePaymentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
        monthly_expense_id = self.request.query_params.get('monthly_expense')
        if monthly_expense_id:
            queryset = queryset.filter(monthly_expense_id=monthly_expense_id)
        
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(monthly_expense__fixed_expense__category_id=category_id)
        
        payment_method = self.request.query_params.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        
        # Filtro por rango de fechas
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(payment_date__lte=end_date)
        
        return queryset

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Estadísticas de pagos"""
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        queryset = self.get_queryset()
        
        if start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(payment_date__lte=end_date)
        
        total_payments = queryset.count()
        total_amount = queryset.aggregate(total=Sum('amount'))['total'] or 0
        
        # Pagos por método
        payments_by_method = queryset.values('payment_method').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Pagos por categoría
        payments_by_category = queryset.values(
            'monthly_expense__fixed_expense__category__name'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        return Response({
            'total_payments': total_payments,
            'total_amount': total_amount,
            'payments_by_method': payments_by_method,
            'payments_by_category': payments_by_category,
        })


class VariableExpenseViewSet(BaseModelViewSet):
    queryset = VariableExpense.objects.all()
    serializer_class = VariableExpenseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        payment_method = self.request.query_params.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        
        # Filtro por rango de fechas
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(expense_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(expense_date__lte=end_date)
        
        # Búsqueda por nombre
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Estadísticas de gastos variables"""
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        queryset = self.get_queryset()
        
        if start_date:
            queryset = queryset.filter(expense_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(expense_date__lte=end_date)
        
        total_expenses = queryset.count()
        total_amount = queryset.aggregate(total=Sum('amount'))['total'] or 0
        
        # Gastos por categoría
        expenses_by_category = queryset.values('category__name').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Gastos por método de pago
        expenses_by_payment_method = queryset.values('payment_method').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        return Response({
            'total_expenses': total_expenses,
            'total_amount': total_amount,
            'expenses_by_category': expenses_by_category,
            'expenses_by_payment_method': expenses_by_payment_method,
        })
