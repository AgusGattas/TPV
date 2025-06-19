import django_filters
from sales.models import Sale

class SaleFilter(django_filters.FilterSet):
    ticket_number = django_filters.CharFilter(lookup_expr='icontains')
    payment_method = django_filters.ChoiceFilter(choices=Sale.PAYMENT_METHODS)
    is_active = django_filters.BooleanFilter()
    
    total_min = django_filters.NumberFilter(field_name='total_final', lookup_expr='gte')
    total_max = django_filters.NumberFilter(field_name='total_final', lookup_expr='lte')
    
    created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    user_email = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    cashbox_id = django_filters.NumberFilter(field_name='cashbox__id')

    class Meta:
        model = Sale
        fields = {
            'ticket_number': ['exact', 'icontains'],
            'payment_method': ['exact'],
            'is_active': ['exact'],
            'total_final': ['exact', 'gte', 'lte'],
            'subtotal': ['exact', 'gte', 'lte'],
            'total_discount': ['exact', 'gte', 'lte'],
            'created_at': ['exact', 'gte', 'lte'],
            'user': ['exact'],
            'cashbox': ['exact'],
        } 