from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from products.models import Product, ProductImage



class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "created_at", "updated_at"]


class ProductListSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    stock_status = serializers.ReadOnlyField()
    current_stock = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "barcode",
            "price",
            "cost_price",
            "current_stock",
            "min_stock",
            "stock_status",
            "is_active",
            "description",
            "unit",
            "images",
            "created_at",
            "updated_at",
        ]


class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "barcode",
            "name",
            "price",
            "cost_price",
            "min_stock",
            "is_active",
            "description",
            "unit",
        ]


class ProductUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "name",
            "barcode",
            "price",
            "cost_price",
            "min_stock",
            "is_active",
            "description",
            "unit",
        ]

