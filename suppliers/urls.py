from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SupplierViewSet, SupplierInvoiceViewSet, SupplierPaymentViewSet

router = DefaultRouter()
router.register(r'suppliers', SupplierViewSet)
router.register(r'invoices', SupplierInvoiceViewSet)
router.register(r'payments', SupplierPaymentViewSet)

urlpatterns = [
    path('', include(router.urls)),
] 