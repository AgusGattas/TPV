import django_filters
from stock.models import Stock, StockMovement

class StockFilter(django_filters.FilterSet):
    product_name = django_filters.CharFilter(field_name='product__name', lookup_expr='icontains')
    product_barcode = django_filters.CharFilter(field_name='product__barcode', lookup_expr='icontains')
    
    current_quantity_min = django_filters.NumberFilter(field_name='current_quantity', lookup_expr='gte')
    current_quantity_max = django_filters.NumberFilter(field_name='current_quantity', lookup_expr='lte')
    
    average_cost_min = django_filters.NumberFilter(field_name='average_cost', lookup_expr='gte')
    average_cost_max = django_filters.NumberFilter(field_name='average_cost', lookup_expr='lte')
    
    created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = Stock
        fields = {
            'product': ['exact'],
            'current_quantity': ['exact', 'gte', 'lte'],
            'average_cost': ['exact', 'gte', 'lte'],
            'created_at': ['exact', 'gte', 'lte'],
        }


class StockMovementFilter(django_filters.FilterSet):
    type = django_filters.ChoiceFilter(choices=StockMovement.MOVEMENT_TYPES)
    reason = django_filters.CharFilter(lookup_expr='icontains')
    sale_id = django_filters.NumberFilter(field_name='sale__id')
    product_name = django_filters.CharFilter(field_name='stock__product__name', lookup_expr='icontains')
    
    quantity_min = django_filters.NumberFilter(field_name='quantity', lookup_expr='gte')
    quantity_max = django_filters.NumberFilter(field_name='quantity', lookup_expr='lte')
    
    cost_price_min = django_filters.NumberFilter(field_name='cost_price', lookup_expr='gte')
    cost_price_max = django_filters.NumberFilter(field_name='cost_price', lookup_expr='lte')
    
    created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = StockMovement
        fields = {
            'stock': ['exact'],
            'type': ['exact'],
            'reason': ['exact', 'icontains'],
            'sale': ['exact'],
            'quantity': ['exact', 'gte', 'lte'],
            'cost_price': ['exact', 'gte', 'lte'],
            'created_at': ['exact', 'gte', 'lte'],
        } 