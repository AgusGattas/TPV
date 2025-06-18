from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from products.models import Product, ProductImage



class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("image",)


class ProductListSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "price",
            "stock",
            "is_active",
            "image",
            "created_at",
            "updated_at",
        )

    def get_image(self, obj):
        return ProductImageSerializer(obj.images.first(), context=self.context).data[
            "image"
        ]

