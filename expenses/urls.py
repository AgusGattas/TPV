from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExpenseCategoryViewSet, FixedExpenseViewSet, MonthlyExpenseViewSet,
    ExpensePaymentViewSet, VariableExpenseViewSet
)

router = DefaultRouter()
router.register(r'categories', ExpenseCategoryViewSet)
router.register(r'fixed-expenses', FixedExpenseViewSet)
router.register(r'monthly-expenses', MonthlyExpenseViewSet)
router.register(r'payments', ExpensePaymentViewSet)
router.register(r'variable-expenses', VariableExpenseViewSet)

urlpatterns = [
    path('', include(router.urls)),
] 