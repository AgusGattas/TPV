from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Q, Count
from django.utils import timezone
from datetime import datetime, timedelta

from django_base.base_utils.base_viewsets import BaseModelViewSet
from .models import Supplier, SupplierInvoice, SupplierPayment
from .serializers import (
    SupplierSerializer, SupplierDetailSerializer,
    SupplierInvoiceSerializer, SupplierInvoiceDetailSerializer,
    SupplierPaymentSerializer
)


class SupplierViewSet(BaseModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    
    serializers = {
        "retrieve": SupplierDetailSerializer,
        "list": SupplierSerializer,
        "default": SupplierSerializer,
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
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(cuit__icontains=search) |
                Q(email__icontains=search)
            )
        
        return queryset

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Estadísticas generales de proveedores"""
        total_suppliers = Supplier.objects.filter(is_active=True).count()
        total_pending = Supplier.objects.aggregate(
            total=Sum('invoices__remaining_amount', filter=Q(invoices__is_paid=False))
        )['total'] or 0
        
        overdue_invoices = SupplierInvoice.objects.filter(
            due_date__lt=timezone.now().date(),
            is_paid=False
        ).count()
        
        return Response({
            'total_suppliers': total_suppliers,
            'total_pending_amount': total_pending,
            'overdue_invoices_count': overdue_invoices,
        })


class SupplierInvoiceViewSet(BaseModelViewSet):
    queryset = SupplierInvoice.objects.all()
    serializer_class = SupplierInvoiceSerializer
    
    serializers = {
        "retrieve": SupplierInvoiceDetailSerializer,
        "list": SupplierInvoiceSerializer,
        "default": SupplierInvoiceSerializer,
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
        supplier_id = self.request.query_params.get('supplier')
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        
        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        is_paid = self.request.query_params.get('is_paid')
        if is_paid is not None:
            queryset = queryset.filter(is_paid=is_paid.lower() == 'true')
        
        # Filtro por rango de fechas
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(invoice_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(invoice_date__lte=end_date)
        
        return queryset

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Facturas vencidas"""
        overdue_invoices = self.get_queryset().filter(
            due_date__lt=timezone.now().date(),
            is_paid=False
        )
        serializer = self.get_serializer(overdue_invoices, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Estadísticas de facturas"""
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        queryset = self.get_queryset()
        
        if start_date:
            queryset = queryset.filter(invoice_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(invoice_date__lte=end_date)
        
        total_invoices = queryset.count()
        total_amount = queryset.aggregate(total=Sum('total_amount'))['total'] or 0
        paid_amount = queryset.filter(is_paid=True).aggregate(total=Sum('total_amount'))['total'] or 0
        pending_amount = total_amount - paid_amount
        
        return Response({
            'total_invoices': total_invoices,
            'total_amount': total_amount,
            'paid_amount': paid_amount,
            'pending_amount': pending_amount,
        })


class SupplierPaymentViewSet(BaseModelViewSet):
    queryset = SupplierPayment.objects.all()
    serializer_class = SupplierPaymentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
        supplier_id = self.request.query_params.get('supplier')
        if supplier_id:
            queryset = queryset.filter(invoice__supplier_id=supplier_id)
        
        invoice_id = self.request.query_params.get('invoice')
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)
        
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
        
        return Response({
            'total_payments': total_payments,
            'total_amount': total_amount,
            'payments_by_method': payments_by_method,
        })
