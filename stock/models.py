from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from products.models import Product
from django_base.base_utils.base_models import BaseModel
from decimal import Decimal


class Stock(BaseModel):
    """
    Modelo simplificado para manejar el stock de productos
    """
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_info',
        verbose_name=_("Product")
    )
    current_quantity = models.IntegerField(_("Current Quantity"), default=0)
    average_cost = models.DecimalField(_("Average Cost"), max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        verbose_name = _("Stock")
        verbose_name_plural = _("Stocks")

    def __str__(self):
        return f"{self.product.name} - Stock: {self.current_quantity}"

    def add_stock(self, quantity, cost_price, reason="Compra"):
        """Agrega stock al producto"""
        if quantity <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        
        # Calcular nuevo precio promedio
        total_cost = (self.current_quantity * self.average_cost) + (quantity * cost_price)
        total_quantity = self.current_quantity + quantity
        
        if total_quantity > 0:
            self.average_cost = total_cost / total_quantity
        
        self.current_quantity = total_quantity
        self.save()
        
        # Crear movimiento de stock
        StockMovement.objects.create(
            stock=self,
            type='ingreso',
            quantity=quantity,
            cost_price=cost_price,
            reason=reason
        )

    def remove_stock(self, quantity, reason="Venta"):
        """Remueve stock del producto"""
        if quantity <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        
        if self.current_quantity < quantity:
            raise ValueError(f"Stock insuficiente. Disponible: {self.current_quantity}, Solicitado: {quantity}")
        
        self.current_quantity -= quantity
        self.save()
        
        # Crear movimiento de stock
        StockMovement.objects.create(
            stock=self,
            type='egreso',
            quantity=quantity,
            cost_price=self.average_cost,
            reason=reason
        )

    def return_stock(self, quantity, reason="Devolución a proveedor"):
        """Devuelve stock al proveedor"""
        if quantity <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        
        if self.current_quantity < quantity:
            raise ValueError(f"Stock insuficiente para devolución. Disponible: {self.current_quantity}, Solicitado: {quantity}")
        
        self.current_quantity -= quantity
        self.save()
        
        # Crear movimiento de stock
        StockMovement.objects.create(
            stock=self,
            type='devolucion',
            quantity=quantity,
            cost_price=self.average_cost,
            reason=reason
        )


class StockMovement(BaseModel):
    """
    Historial de movimientos de stock
    """
    MOVEMENT_TYPES = (
        ('ingreso', _('Ingreso')),
        ('egreso', _('Egreso')),
        ('devolucion', _('Devolución')),
    )

    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name='movements',
        verbose_name=_("Stock")
    )
    type = models.CharField(_("Type"), max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(_("Quantity"))
    cost_price = models.DecimalField(_("Cost Price"), max_digits=10, decimal_places=2)
    reason = models.CharField(_("Reason"), max_length=255)
    sale = models.ForeignKey(
        'sales.Sale',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        verbose_name=_("Sale")
    )

    class Meta:
        verbose_name = _("Stock Movement")
        verbose_name_plural = _("Stock Movements")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_type_display()} - {self.quantity} - {self.created_at}"
