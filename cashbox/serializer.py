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
    suggested_initial_cash = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        read_only=True,
        help_text="Efectivo inicial sugerido basado en la última caja cerrada"
    )

    class Meta:
        model = CashBox
        fields = [
            'user',
            'initial_cash',
            'suggested_initial_cash',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-llenar initial_cash con el cash_to_keep de la última caja cerrada
        if not self.instance:  # Solo si es una nueva instancia
            suggested_cash = CashBox.get_suggested_initial_cash()
            self.fields['initial_cash'].default = suggested_cash
            self.fields['initial_cash'].initial = suggested_cash

    def to_representation(self, instance):
        """Agregar el suggested_initial_cash a la respuesta"""
        data = super().to_representation(instance)
        data['suggested_initial_cash'] = CashBox.get_suggested_initial_cash()
        return data

    def validate(self, data):
        """Validar que no haya cajas abiertas"""
        if CashBox.objects.filter(closed_at__isnull=True).exists():
            raise serializers.ValidationError(
                "No se puede abrir una nueva caja mientras haya una caja abierta"
            )
        
        # Validar que el efectivo inicial sea positivo
        if data['initial_cash'] <= 0:
            raise serializers.ValidationError("El efectivo inicial debe ser mayor a 0")
        
        return data


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
        help_text="Efectivo a mantener en caja para la próxima apertura (opcional, si no se especifica se mantiene todo el efectivo contado)"
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
        
        # Validar que cash_to_keep no sea mayor que counted_cash
        cash_to_keep = data.get('cash_to_keep')
        if cash_to_keep is not None and cash_to_keep > data['counted_cash']:
            raise serializers.ValidationError(
                "El efectivo a mantener no puede ser mayor al efectivo contado"
            )
        
        return data

    def to_representation(self, instance):
        """Agregar información adicional sobre el cierre"""
        data = super().to_representation(instance)
        
        # Calcular valores si la caja está cerrada
        if instance.closed_at:
            data.update({
                'cash_to_withdraw': instance.cash_to_withdraw,
                'difference': instance.difference,
                'closed_at': instance.closed_at,
                'calculated_cash': instance.calculated_cash,
                'total_sales': instance.total_sales,
                'total_movements': instance.total_movements
            })
        
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

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a 0")
        return value

    def validate(self, data):
        # Validaciones adicionales si es necesario
        return data 