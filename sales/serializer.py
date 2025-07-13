from rest_framework import serializers
from sales.models import Sale, SaleItem
from products.serializer import ProductListSerializer
from products.models import Product
from stock.models import Stock

class SaleItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    discount_amount = serializers.ReadOnlyField()
    total = serializers.ReadOnlyField()

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "product",
            "product_id",
            "quantity",
            "unit_price",
            "discount_percentage",
            "subtotal",
            "discount_amount",
            "total",
            "created_at",
            "updated_at",
        ]

class SaleItemCreateSerializer(serializers.Serializer):
    """
    Serializer específico para crear items de venta
    """
    product_id = serializers.IntegerField(
        help_text="ID del producto (obligatorio)"
    )
    quantity = serializers.IntegerField(
        min_value=1,
        help_text="Cantidad del producto (obligatorio, mínimo 1)"
    )
    unit_price = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        help_text="Precio unitario (opcional, si no se envía usa el precio del producto)"
    )
    discount_percentage = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        help_text="Porcentaje de descuento (opcional, default 0)"
    )

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    items_data = serializers.ListField(
        child=SaleItemCreateSerializer(),
        write_only=True,
        required=False
    )
    user_name = serializers.CharField(source='user.email', read_only=True)
    cashbox_name = serializers.CharField(source='cashbox.id', read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "ticket_number",
            "user",
            "user_name",
            "cashbox",
            "cashbox_name",
            "subtotal",
            "total_discount",
            "total_final",
            "payment_method",
            "notes",
            "is_active",
            "items",
            "items_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["ticket_number", "subtotal", "total_discount", "total_final"]

class SaleCreateSerializer(serializers.ModelSerializer):
    items_data = serializers.ListField(
        child=SaleItemCreateSerializer(),
        write_only=True,
        help_text="Lista de productos a vender"
    )

    class Meta:
        model = Sale
        fields = [
            "cashbox",
            "payment_method", 
            "notes",
            "items_data",
        ]
        extra_kwargs = {
            'cashbox': {
                'help_text': 'ID de la caja registradora'
            },
            'payment_method': {
                'help_text': 'Método de pago: efectivo, transferencia, debito, credito, qr'
            },
            'notes': {
                'help_text': 'Notas adicionales de la venta (opcional)'
            }
        }

    def validate_items_data(self, value):
        """Validar que cada item tenga product_id y quantity, y verificar stock disponible"""
        if not value:
            raise serializers.ValidationError("Debe incluir al menos un item")
        
        stock_errors = []
        
        for index, item in enumerate(value):
            # Validaciones básicas
            if 'product_id' not in item:
                raise serializers.ValidationError("Cada item debe incluir product_id")
            if 'quantity' not in item:
                raise serializers.ValidationError("Cada item debe incluir quantity")
            if item['quantity'] <= 0:
                raise serializers.ValidationError("La cantidad debe ser mayor a 0")
            
            # Validar que el producto existe y está activo
            try:
                product = Product.objects.get(id=item['product_id'], is_active=True)
            except Product.DoesNotExist:
                stock_errors.append(f"Item {index + 1}: El producto con ID {item['product_id']} no existe o no está activo")
                continue
            
            # Validar stock disponible
            try:
                stock = Stock.objects.get(product=product)
                current_stock = stock.current_quantity
                
                if current_stock <= 0:
                    stock_errors.append(f"Item {index + 1}: {product.name} - Sin stock disponible (stock actual: {current_stock})")
                elif current_stock < item['quantity']:
                    stock_errors.append(f"Item {index + 1}: {product.name} - Stock insuficiente (disponible: {current_stock}, solicitado: {item['quantity']})")
                    
            except Stock.DoesNotExist:
                stock_errors.append(f"Item {index + 1}: {product.name} - Sin registro de stock disponible")
        
        # Si hay errores de stock, lanzar excepción con todos los errores
        if stock_errors:
            raise serializers.ValidationError({
                "stock_errors": stock_errors,
                "message": "Hay productos sin stock suficiente para completar la venta"
            })
        
        return value

    def create(self, validated_data):
        items_data = validated_data.pop('items_data')
        
        # Asignar el usuario actual automáticamente si está autenticado
        if hasattr(self.context['request'], 'user') and self.context['request'].user.is_authenticated:
            validated_data['user'] = self.context['request'].user
        else:
            # Si no hay usuario autenticado, usar un usuario por defecto o crear uno
            from users.models import User
            try:
                # Intentar obtener el primer usuario disponible
                default_user = User.objects.first()
                if default_user:
                    validated_data['user'] = default_user
                else:
                    # Crear un usuario por defecto si no existe ninguno
                    default_user = User.objects.create_user(
                        email="vendedor@default.com",
                        password="default123",
                        first_name="Vendedor",
                        last_name="Default",
                        role="vendedor"
                    )
                    validated_data['user'] = default_user
            except Exception as e:
                raise serializers.ValidationError(f"No se pudo asignar un usuario: {str(e)}")
        
        # Crear la venta primero (sin calcular totales)
        sale = Sale.objects.create(**validated_data)
        
        # Crear los items después de que la venta tenga ID
        for item_data in items_data:
            SaleItem.objects.create(sale=sale, **item_data)
        
        # Refrescar la venta para obtener los totales calculados
        sale.refresh_from_db()
        return sale

class SaleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = [
            "payment_method",
            "notes",
        ] 