import django_filters
from cashbox.models import CashBox, CashMovement

class CashBoxFilter(django_filters.FilterSet):
    user_email = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    is_open = django_filters.BooleanFilter(method='filter_is_open')
    
    opened_at_after = django_filters.DateTimeFilter(field_name='opened_at', lookup_expr='gte')
    opened_at_before = django_filters.DateTimeFilter(field_name='opened_at', lookup_expr='lte')
    
    closed_at_after = django_filters.DateTimeFilter(field_name='closed_at', lookup_expr='gte')
    closed_at_before = django_filters.DateTimeFilter(field_name='closed_at', lookup_expr='lte')
    
    initial_cash_min = django_filters.NumberFilter(field_name='initial_cash', lookup_expr='gte')
    initial_cash_max = django_filters.NumberFilter(field_name='initial_cash', lookup_expr='lte')

    def filter_is_open(self, queryset, name, value):
        if value:
            return queryset.filter(closed_at__isnull=True)
        return queryset.filter(closed_at__isnull=False)

    class Meta:
        model = CashBox
        fields = {
            'user': ['exact'],
            'initial_cash': ['exact', 'gte', 'lte'],
            'calculated_cash': ['exact', 'gte', 'lte'],
            'counted_cash': ['exact', 'gte', 'lte'],
            'difference': ['exact', 'gte', 'lte'],
            'opened_at': ['exact', 'gte', 'lte'],
            'closed_at': ['exact', 'gte', 'lte'],
        }


class CashMovementFilter(django_filters.FilterSet):
    type = django_filters.ChoiceFilter(choices=CashMovement.MOVEMENT_TYPES)
    cashbox_id = django_filters.NumberFilter(field_name='cashbox__id')
    user_email = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    reason = django_filters.CharFilter(lookup_expr='icontains')
    
    amount_min = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    
    created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = CashMovement
        fields = {
            'cashbox': ['exact'],
            'user': ['exact'],
            'type': ['exact'],
            'amount': ['exact', 'gte', 'lte'],
            'reason': ['exact', 'icontains'],
            'created_at': ['exact', 'gte', 'lte'],
        } 