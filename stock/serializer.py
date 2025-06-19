from rest_framework import serializers
from stock.models import Stock, StockMovement
from products.serializer import ProductListSerializer


class StockMovementSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id',
            'type',
            'type_display',
            'quantity',
            'cost_price',
            'reason',
            'sale',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['sale']


class StockSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    movements = StockMovementSerializer(many=True, read_only=True)

    class Meta:
        model = Stock
        fields = [
            'id',
            'product',
            'current_quantity',
            'average_cost',
            'movements',
            'created_at',
            'updated_at',
        ]


class StockAddSerializer(serializers.Serializer):
    """
    Serializer para agregar stock a un producto
    """
    quantity = serializers.IntegerField(
        min_value=1,
        help_text="Cantidad a agregar (mínimo 1)"
    )
    cost_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Precio de compra por unidad"
    )
    reason = serializers.CharField(
        max_length=255,
        required=False,
        default="Compra",
        help_text="Motivo del ingreso de stock"
    )


class StockReturnSerializer(serializers.Serializer):
    """
    Serializer para devolver stock al proveedor
    """
    quantity = serializers.IntegerField(
        min_value=1,
        help_text="Cantidad a devolver (mínimo 1)"
    )
    reason = serializers.CharField(
        max_length=255,
        required=False,
        default="Devolución a proveedor",
        help_text="Motivo de la devolución"
    )


class StockProductSerializer(serializers.ModelSerializer):
    """
    Serializer para mostrar stock de un producto específico
    """
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_barcode = serializers.CharField(source='product.barcode', read_only=True)
    product_unit = serializers.CharField(source='product.unit', read_only=True)

    class Meta:
        model = Stock
        fields = [
            'id',
            'product_name',
            'product_barcode',
            'product_unit',
            'current_quantity',
            'average_cost',
            'created_at',
            'updated_at',
        ] 