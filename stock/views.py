from django.shortcuts import render
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
from django.db.models import Sum, Count, Q, F
from stock.models import Stock, StockMovement
from products.models import Product
from rest_framework.permissions import AllowAny
from stock.serializer import (
    StockSerializer,
    StockMovementSerializer,
    StockAddSerializer,
    StockReturnSerializer,
    StockProductSerializer
)
from stock.filters import StockFilter, StockMovementFilter
from django_base.base_utils.base_viewsets import BaseGenericViewSet

# Create your views here.

class StockViewSet(
    BaseGenericViewSet,
    ListModelMixin,
    RetrieveModelMixin,
):
    filter_backends = (
        filters.DjangoFilterBackend,
        rest_filters.SearchFilter,
        rest_filters.OrderingFilter,
    )

    # filterset_class = StockFilter

    search_fields = (
        "product__name",
        "product__barcode",
    )

    ordering = ("-created_at",)

    ordering_fields = ("id", "current_quantity", "average_cost", "created_at")

    serializers = {
        "list": StockSerializer,
        "retrieve": StockSerializer,
        "add_stock": StockAddSerializer,
        "return_stock": StockReturnSerializer,
        "default": StockSerializer,
    }

    permissions = {
        "list": [AllowAny],
        "retrieve": [AllowAny],
        "default": [AllowAny],
    }

    def get_queryset(self):
        return (
            Stock.objects.select_related("product")
            .prefetch_related("movements")
            .all()
            .order_by("-created_at")
        )

    @action(detail=True, methods=['post'])
    def add_stock(self, request, pk=None):
        """Agregar stock a un producto"""
        stock = self.get_object()
        serializer = StockAddSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                stock.add_stock(
                    quantity=serializer.validated_data['quantity'],
                    cost_price=serializer.validated_data['cost_price'],
                    reason=serializer.validated_data.get('reason', 'Compra')
                )
                return Response({"message": "Stock agregado exitosamente"}, status=status.HTTP_200_OK)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def return_stock(self, request, pk=None):
        """Devolver stock al proveedor"""
        stock = self.get_object()
        serializer = StockReturnSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                stock.return_stock(
                    quantity=serializer.validated_data['quantity'],
                    reason=serializer.validated_data.get('reason', 'Devolución a proveedor')
                )
                return Response({"message": "Stock devuelto exitosamente"}, status=status.HTTP_200_OK)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        """Ver historial de movimientos de un producto"""
        stock = self.get_object()
        movements = stock.movements.all()
        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='by-product/(?P<product_id>[^/.]+)')
    def by_product(self, request, product_id=None):
        """Obtener stock de un producto específico"""
        if not product_id:
            return Response(
                {"error": "Se requiere el parámetro product_id"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            stock = Stock.objects.get(product_id=product_id)
            serializer = StockProductSerializer(stock)
            return Response(serializer.data)
        except Stock.DoesNotExist:
            return Response(
                {"error": "Stock no encontrado para este producto"}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Productos con stock bajo"""
        stocks = self.get_queryset().filter(
            current_quantity__lte=F('product__min_stock')
        )
        serializer = StockProductSerializer(stocks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        """Productos sin stock"""
        stocks = self.get_queryset().filter(current_quantity=0)
        serializer = StockProductSerializer(stocks, many=True)
        return Response(serializer.data)


class StockMovementViewSet(
    BaseGenericViewSet,
    ListModelMixin,
    RetrieveModelMixin,
):
    filter_backends = (
        filters.DjangoFilterBackend,
        rest_filters.SearchFilter,
        rest_filters.OrderingFilter,
    )

    # filterset_class = StockMovementFilter

    search_fields = (
        "reason",
        "stock__product__name",
    )

    ordering = ("-created_at",)

    ordering_fields = ("id", "type", "quantity", "created_at")

    serializers = {
        "list": StockMovementSerializer,
        "retrieve": StockMovementSerializer,
        "default": StockMovementSerializer,
    }

    permissions = {
        "list": [AllowAny],
        "retrieve": [AllowAny],
        "default": [AllowAny],
    }

    def get_queryset(self):
        return (
            StockMovement.objects.select_related("stock__product")
            .all()
            .order_by("-created_at")
        )

    @action(detail=False, methods=['get'])
    def by_product(self, request):
        """Movimientos de un producto específico"""
        product_id = request.query_params.get('product_id')
        
        if not product_id:
            return Response(
                {"error": "Se requiere el parámetro product_id"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        movements = self.get_queryset().filter(stock__product_id=product_id)
        serializer = self.get_serializer(movements, many=True)
        return Response(serializer.data)
