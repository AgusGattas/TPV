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
from rest_framework.exceptions import ValidationError

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

    def create(self, request, *args, **kwargs):
        """Crear una venta con manejo mejorado de errores de stock"""
        try:
            return super().create(request, *args, **kwargs)
        except ValidationError as e:
            # Manejar errores de validación de stock específicamente
            if hasattr(e, 'detail') and isinstance(e.detail, dict) and 'items_data' in e.detail:
                items_data_error = e.detail['items_data']
                if isinstance(items_data_error, dict) and 'stock_errors' in items_data_error:
                    return Response({
                        "error": "Error de stock",
                        "message": items_data_error.get('message', 'Hay productos sin stock suficiente'),
                        "stock_errors": items_data_error['stock_errors'],
                        "details": "Verifique el stock disponible de los productos antes de realizar la venta"
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Para otros errores de validación, simplificar el formato
            error_messages = []
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                for field, errors in e.detail.items():
                    if isinstance(errors, list):
                        for error in errors:
                            error_messages.append(f"{field}: {error}")
                    else:
                        error_messages.append(f"{field}: {errors}")
            else:
                error_messages.append(str(e.detail))
            
            return Response({
                "error": "Error de validación",
                "message": "Hay errores en los datos proporcionados",
                "details": error_messages
            }, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            # Manejar errores de validación del modelo
            return Response({
                "error": "Error de stock",
                "message": str(e),
                "details": "Verifique que todos los productos tengan stock suficiente"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Manejar otros errores inesperados
            return Response({
                "error": "Error interno del servidor",
                "message": "Ocurrió un error inesperado al procesar la venta",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

    @action(detail=False, methods=['post'])
    def check_stock(self, request):
        """Verificar stock disponible para una lista de productos"""
        items_data = request.data.get('items_data', [])
        
        if not items_data:
            return Response({
                "error": "Datos requeridos",
                "message": "Debe proporcionar items_data con la lista de productos"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        stock_check_results = []
        has_errors = False
        
        for index, item in enumerate(items_data):
            product_id = item.get('product_id')
            quantity = item.get('quantity', 0)
            
            if not product_id:
                stock_check_results.append({
                    "item_index": index + 1,
                    "error": "product_id es requerido"
                })
                has_errors = True
                continue
            
            if quantity <= 0:
                stock_check_results.append({
                    "item_index": index + 1,
                    "error": "quantity debe ser mayor a 0"
                })
                has_errors = True
                continue
            
            try:
                from products.models import Product
                from stock.models import Stock
                
                # Verificar que el producto existe y está activo
                try:
                    product = Product.objects.get(id=product_id, is_active=True)
                except Product.DoesNotExist:
                    stock_check_results.append({
                        "item_index": index + 1,
                        "product_id": product_id,
                        "error": "Producto no existe o no está activo"
                    })
                    has_errors = True
                    continue
                
                # Verificar stock disponible
                try:
                    stock = Stock.objects.get(product=product)
                    current_stock = stock.current_quantity
                    
                    if current_stock <= 0:
                        stock_check_results.append({
                            "item_index": index + 1,
                            "product_id": product_id,
                            "product_name": product.name,
                            "current_stock": current_stock,
                            "requested_quantity": quantity,
                            "status": "sin_stock",
                            "error": f"Sin stock disponible (stock actual: {current_stock})"
                        })
                        has_errors = True
                    elif current_stock < quantity:
                        stock_check_results.append({
                            "item_index": index + 1,
                            "product_id": product_id,
                            "product_name": product.name,
                            "current_stock": current_stock,
                            "requested_quantity": quantity,
                            "status": "stock_insuficiente",
                            "error": f"Stock insuficiente (disponible: {current_stock}, solicitado: {quantity})"
                        })
                        has_errors = True
                    else:
                        stock_check_results.append({
                            "item_index": index + 1,
                            "product_id": product_id,
                            "product_name": product.name,
                            "current_stock": current_stock,
                            "requested_quantity": quantity,
                            "status": "ok",
                            "available": True
                        })
                        
                except Stock.DoesNotExist:
                    stock_check_results.append({
                        "item_index": index + 1,
                        "product_id": product_id,
                        "product_name": product.name,
                        "error": "Sin registro de stock disponible"
                    })
                    has_errors = True
                    
            except Exception as e:
                stock_check_results.append({
                    "item_index": index + 1,
                    "product_id": product_id,
                    "error": f"Error al verificar stock: {str(e)}"
                })
                has_errors = True
        
        return Response({
            "has_errors": has_errors,
            "can_proceed": not has_errors,
            "results": stock_check_results,
            "message": "Verificación de stock completada" if not has_errors else "Hay productos sin stock suficiente"
        }, status=status.HTTP_200_OK if not has_errors else status.HTTP_400_BAD_REQUEST)


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
