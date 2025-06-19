from rest_framework import serializers
from cashbox.models import CashBox, CashMovement
from sales.serializer import SaleSerializer


class CashMovementSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.email', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = CashMovement
        fields = [
            'id',
            'cashbox',
            'user',
            'user_name',
            'type',
            'type_display',
            'amount',
            'reason',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['user']


class CashBoxSerializer(serializers.ModelSerializer):
    movements = CashMovementSerializer(many=True, read_only=True)
    sales = SaleSerializer(many=True, read_only=True)
    user_name = serializers.CharField(source='user.email', read_only=True)
    is_open = serializers.ReadOnlyField()
    total_sales = serializers.ReadOnlyField()
    total_movements = serializers.ReadOnlyField()
    calculated_cash = serializers.ReadOnlyField()

    class Meta:
        model = CashBox
        fields = [
            'id',
            'user',
            'user_name',
            'opened_at',
            'initial_cash',
            'closed_at',
            'calculated_cash',
            'counted_cash',
            'difference',
            'cash_to_keep',
            'cash_to_withdraw',
            'is_open',
            'total_sales',
            'total_movements',
            'movements',
            'sales',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'opened_at', 
            'closed_at',
            'calculated_cash', 
            'difference', 
            'cash_to_keep', 
            'cash_to_withdraw',
            'counted_cash'
        ]


class CashBoxCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashBox
        fields = [
            'user',
            'initial_cash',
        ]


class CashBoxCloseSerializer(serializers.ModelSerializer):
    counted_cash = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Efectivo contado al cierre de caja"
    )
    cash_to_keep = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        required=False,
        help_text="Efectivo a mantener en caja (opcional)"
    )

    class Meta:
        model = CashBox
        fields = [
            'counted_cash',
            'cash_to_keep',
        ]

    def validate(self, data):
        cashbox = self.instance
        if not cashbox.is_open:
            raise serializers.ValidationError("La caja ya está cerrada")
        
        # Validar que el efectivo contado sea positivo
        if data['counted_cash'] <= 0:
            raise serializers.ValidationError("El efectivo contado debe ser mayor a 0")
        
        return data


class CashMovementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashMovement
        fields = [
            'cashbox',
            'type',
            'amount',
            'reason',
        ]

    def validate_cashbox(self, value):
        if not value.is_open:
            raise serializers.ValidationError("No se pueden hacer movimientos en una caja cerrada")
        return value 