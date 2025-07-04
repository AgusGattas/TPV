# Señales para integración automática
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Stock, StockMovement
from products.models import Product


@receiver(post_save, sender=Product)
def create_stock_on_product_creation(sender, instance, created, **kwargs):
    """Crear stock automáticamente cuando se crea un producto"""
    if created:
        # Crear objeto Stock si no existe
        stock_obj, created_stock = Stock.objects.get_or_create(
            product=instance,
            defaults={
                'current_quantity': 0,
                'average_cost': instance.cost_price
            }
        )



@receiver(post_save, sender='sales.Sale')
def reverse_stock_on_sale_cancel(sender, instance, **kwargs):
    """Revertir stock cuando se cancela una venta"""
    if not instance.is_active:
        for sale_item in instance.items.all():
            try:
                stock_obj = sale_item.product.stock_info
                stock_obj.add_stock(
                    quantity=sale_item.quantity,
                    cost_price=sale_item.unit_price,
                    reason=f'Devolución por cancelación de venta #{instance.ticket_number}'
                )
            except Stock.DoesNotExist:
                # Si no existe stock, crear uno
                stock_obj = Stock.objects.create(
                    product=sale_item.product,
                    current_quantity=sale_item.quantity,
                    average_cost=sale_item.unit_price
                )
                stock_obj.add_stock(
                    quantity=sale_item.quantity,
                    cost_price=sale_item.unit_price,
                    reason=f'Devolución por cancelación de venta #{instance.ticket_number}'
                ) 