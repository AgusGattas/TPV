from rest_framework.mixins import (
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
)
from rest_framework import filters as rest_filters
from django_filters import rest_framework as filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Sum, Q, F
from products.models import Product, ProductImage
from rest_framework.permissions import AllowAny
from products.filters import ProductFilter
from products.serializer import ProductListSerializer, ProductCreateSerializer, ProductUpdateSerializer, ProductImageSerializer
from django_base.base_utils.base_viewsets import BaseGenericViewSet

# Create your views here.

class ProductViewSet(
    BaseGenericViewSet,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
):
    filter_backends = (
        filters.DjangoFilterBackend,
        rest_filters.SearchFilter,
        rest_filters.OrderingFilter,
    )

    # filterset_class = ProductFilter

    search_fields = (
        "name",
        "barcode",
        "description",
    )

    ordering = ("-created_at",)

    ordering_fields = ("id", "price", "name", "created_at")

    serializers = {
        "list": ProductListSerializer,
        "retrieve": ProductListSerializer,
        "create": ProductCreateSerializer,
        "update": ProductUpdateSerializer,
        "partial_update": ProductUpdateSerializer,
        "default": ProductListSerializer,
    }

    permissions = {
        "list": [AllowAny],
        "retrieve": [AllowAny],
        "create": [AllowAny],
        "update": [AllowAny],
        "partial_update": [AllowAny],
        "destroy": [AllowAny],
        "default": [AllowAny],
    }

    def get_queryset(self):
        return (
            Product.objects.prefetch_related("images")
            .all()
            .order_by("-created_at")
        )

    @action(detail=False, methods=['get'], url_path='by-barcode/(?P<barcode>[^/.]+)')
    def by_barcode(self, request, barcode=None):
        """Buscar producto por código de barras - útil para escáner"""
        try:
            product = Product.objects.get(barcode=barcode, is_active=True)
            serializer = self.get_serializer(product)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response({"error": "Producto no encontrado"}, status=404)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Productos con stock bajo (stock <= min_stock)"""
        products = self.get_queryset().filter(
            stock_info__current_quantity__lte=F('min_stock')
        )
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        """Productos sin stock (stock = 0)"""
        products = self.get_queryset().filter(
            stock_info__current_quantity=0
        )
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    