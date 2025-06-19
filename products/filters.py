from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
import django_filters
from django.db import models

from products.models import Product



class ProductFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    barcode = django_filters.CharFilter(lookup_expr='icontains')
    
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    
    is_active = django_filters.BooleanFilter()
    
    created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = Product
        fields = {
            'name': ['exact', 'icontains'],
            'barcode': ['exact', 'icontains'],
            'price': ['exact', 'gte', 'lte'],
            'cost_price': ['exact', 'gte', 'lte'],
            'min_stock': ['exact', 'gte', 'lte'],
            'is_active': ['exact'],
            'unit': ['exact', 'icontains'],
        }

    def filter_stock_status(self, queryset, name, value):
        if value == 'low':
            return queryset.filter(stock__lte=models.F('min_stock'))
        elif value == 'high':
            return queryset.filter(stock__gte=models.F('max_stock'))
        elif value == 'normal':
            return queryset.filter(
                stock__gt=models.F('min_stock'),
                stock__lt=models.F('max_stock')
            )
        return queryset


