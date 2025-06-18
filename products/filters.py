from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters

from products.models import Product



class ProductFilter(filters.FilterSet):

    class Meta:
        model = Product
        fields = {
            "created_at": ["exact", "gte", "lte"],
            "is_active": ["exact"],

        }


