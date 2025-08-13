from django.core.management.base import BaseCommand
from products.models import Product
from stock.models import Stock, StockMovement
from users.models import User


class Command(BaseCommand):
    help = 'Agrega 40 unidades de stock y establece stock mínimo de 8 a todos los productos activos para testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--quantity',
            type=int,
            default=40,
            help='Cantidad de stock a agregar (default: 40)'
        )
        parser.add_argument(
            '--min-stock',
            type=int,
            default=8,
            help='Stock mínimo a establecer (default: 8)'
        )
        parser.add_argument(
            '--reason',
            type=str,
            default='Stock inicial para testing',
            help='Razón del movimiento de stock'
        )

    def handle(self, *args, **options):
        quantity = options['quantity']
        min_stock = options['min_stock']
        reason = options['reason']
        
        # Obtener el primer usuario superuser para registrar los movimientos
        try:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                self.stdout.write(
                    self.style.ERROR('❌ No se encontró ningún superuser. Creando uno temporal...')
                )
                user = User.objects.create_user(
                    username='temp_admin',
                    email='temp@todobrilla.com',
                    password='temp123',
                    is_superuser=True,
                    is_staff=True
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error al obtener/crear usuario: {e}')
            )
            return
        
        # Obtener todos los productos activos
        products = Product.objects.filter(is_active=True)
        
        if not products.exists():
            self.stdout.write(
                self.style.ERROR('❌ No se encontraron productos activos')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(f'📦 Encontrados {products.count()} productos activos')
        )
        self.stdout.write(
            f'🔄 Agregando {quantity} unidades de stock y estableciendo stock mínimo de {min_stock} a cada producto...'
        )
        
        success_count = 0
        error_count = 0
        
        for product in products:
            try:
                # Establecer stock mínimo
                product.min_stock = min_stock
                product.save()
                
                # Obtener o crear el registro de stock para el producto
                stock, created = Stock.objects.get_or_create(
                    product=product,
                    defaults={'current_quantity': 0, 'average_cost': 0}
                )
                
                # Agregar stock usando el método del modelo
                stock.add_stock(quantity, product.cost_price, reason)
                
                self.stdout.write(
                    f'✅ {product.name}: +{quantity} unidades (Stock: {stock.current_quantity}, Mín: {min_stock})'
                )
                success_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error con {product.name}: {e}')
                )
                error_count += 1
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS(f'🎉 Proceso completado:')
        )
        self.stdout.write(f'   ✅ Productos actualizados: {success_count}')
        self.stdout.write(f'   ❌ Errores: {error_count}')
        self.stdout.write(f'   📊 Total de productos procesados: {success_count + error_count}')
        self.stdout.write(f'   📦 Stock agregado por producto: {quantity} unidades')
        self.stdout.write(f'   🚨 Stock mínimo establecido: {min_stock} unidades')
        
        # Limpiar usuario temporal si se creó
        if user.username == 'temp_admin':
            user.delete()
            self.stdout.write('🧹 Usuario temporal eliminado') 