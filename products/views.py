from rest_framework.mixins import (
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework import filters as rest_filters
from django_filters import rest_framework as filters
from products.models import Product
from rest_framework.permissions import AllowAny
from products.filters import ProductFilter
from products.serializer import ProductListSerializer
from django_base.base_utils.base_viewsets import BaseGenericViewSet

# Create your views here.

class ProductViewSet(
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

    filterset_class = ProductFilter

    search_fields = (
        "name",
        "barcode",
    )

    ordering = ("-id",)

    ordering_fields = ("id", "price", "name", "created_at")

    serializers = {
        "list": ProductListSerializer,
        "retrieve": ProductListSerializer,
        "create": ProductListSerializer,
        "update": ProductListSerializer,
        "partial_update": ProductListSerializer,
        "default": ProductListSerializer,
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
            Product.objects.prefetch_related("images")
            .filter(is_active=True)
            .order_by("-id")
        )
    