from rest_framework.mixins import (
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework import filters as rest_filters
from django_filters import rest_framework as filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Sum, Q, F
from sales.models import Sale, SaleItem
from rest_framework.permissions import AllowAny, IsAuthenticated
from sales.filters import SaleFilter
from sales.serializer import SaleSerializer, SaleCreateSerializer, SaleUpdateSerializer, SaleItemSerializer
from django_base.base_utils.base_viewsets import BaseGenericViewSet

# Create your views here.

class SaleViewSet(
    BaseGenericViewSet,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
):
    filter_backends = (
        filters.DjangoFilterBackend,
        rest_filters.SearchFilter,
        rest_filters.OrderingFilter,
    )

    # filterset_class = SaleFilter

    search_fields = (
        "ticket_number",
        "id",
    )

    ordering = ("-created_at",)

    ordering_fields = ("id", "ticket_number", "total_final", "created_at")

    serializers = {
        "list": SaleSerializer,
        "retrieve": SaleSerializer,
        "create": SaleCreateSerializer,
        "update": SaleUpdateSerializer,
        "partial_update": SaleUpdateSerializer,
        "default": SaleSerializer,
    }

    permissions = {
        "list": [AllowAny],
        "retrieve": [AllowAny],
        "create": [AllowAny],
        "update": [AllowAny],
        "partial_update": [AllowAny],
        "default": [AllowAny],
    }

    def get_queryset(self):
        return (
            Sale.objects.select_related("user", "cashbox")
            .prefetch_related("items__product")
            .filter(is_active=True)
            .order_by("-created_at")
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancelar una venta (soft delete)"""
        sale = self.get_object()
        sale.cancel_sale()
        return Response({"message": "Venta cancelada"}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def by_ticket(self, request, ticket_number=None):
        """Buscar venta por número de ticket"""
        try:
            sale = Sale.objects.filter(is_active=True).get(ticket_number=ticket_number)
            serializer = self.get_serializer(sale)
            return Response(serializer.data)
        except Sale.DoesNotExist:
            return Response({"error": "Venta no encontrada"}, status=404)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Estadísticas de ventas"""
        queryset = self.get_queryset()
        
        # Filtros por fecha si se proporcionan
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        stats = {
            'total_sales': queryset.count(),
            'total_revenue': queryset.aggregate(
                total=Sum('total_final')
            )['total'] or 0,
            'total_discounts': queryset.aggregate(
                total=Sum('total_discount')
            )['total'] or 0,
            'average_sale': queryset.aggregate(
                average=Sum('total_final') / Count('id')
            )['average'] or 0,
        }
        
        return Response(stats)


class SaleItemViewSet(
    BaseGenericViewSet,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
):
    """
    ViewSet para SaleItems - SOLO LECTURA Y ACTUALIZACIÓN
    NO permite crear items sueltos (se crean automáticamente con la venta)
    """
    filter_backends = (
        filters.DjangoFilterBackend,
        rest_filters.SearchFilter,
        rest_filters.OrderingFilter,
    )

    search_fields = (
        "sale__ticket_number",
        "product__name",
    )

    ordering = ("-created_at",)

    ordering_fields = ("id", "quantity", "unit_price", "subtotal", "created_at")

    serializers = {
        "list": SaleItemSerializer,
        "retrieve": SaleItemSerializer,
        "update": SaleItemSerializer,
        "partial_update": SaleItemSerializer,
        "default": SaleItemSerializer,
    }

    permissions = {
        "list": [AllowAny],
        "retrieve": [AllowAny],
        "update": [AllowAny],
        "partial_update": [AllowAny],
        "default": [AllowAny],
    }

    def get_queryset(self):
        return (
            SaleItem.objects.select_related("sale", "product")
            .all()
            .order_by("-created_at")
        )
