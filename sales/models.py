from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from products.models import Product
from django_base.base_utils.base_models import BaseModel


class Sale(BaseModel):
    PAYMENT_METHODS = (
        ('efectivo', _('Cash')),
        ('transferencia', _('Transfer')),
        ('debito', _('Debit Card')),
    )

    user = models.ForeignKey(
        "users.User", 
        on_delete=models.CASCADE,
        related_name='sales',
        verbose_name=_("User")
    )
    cashbox = models.ForeignKey(
        'cashbox.CashBox',
        on_delete=models.PROTECT,
        related_name='sales',
        verbose_name=_("Cash Box")
    )
    ticket_number = models.CharField(_("Ticket Number"), max_length=20, unique=True, blank=True)
    subtotal = models.DecimalField(_("Subtotal"), max_digits=10, decimal_places=2, default=0)
    total_discount = models.DecimalField(_("Total Discount"), max_digits=10, decimal_places=2, default=0)
    total_final = models.DecimalField(_("Total Final"), max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(_("Payment Method"), max_length=20, choices=PAYMENT_METHODS)
    notes = models.TextField(_("Notes"), blank=True, null=True)
    is_active = models.BooleanField(_("Is Active"), default=True)

    class Meta:
        verbose_name = _("Sale")
        verbose_name_plural = _("Sales")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sale #{self.id} - {self.created_at}"

    def save(self, *args, **kwargs):
        # Generar número de ticket automáticamente si no existe
        if not self.ticket_number:
            self.generate_ticket_number()
        
        # Solo calcular totales si la venta ya tiene ID (ya existe)
        if self.pk:
            self.calculate_totals()
        
        super().save(*args, **kwargs)

    def generate_ticket_number(self):
        """Genera un número de ticket único"""
        last_sale = Sale.objects.filter(is_active=True).order_by('-id').first()
        if last_sale and last_sale.ticket_number:
            try:
                last_number = int(last_sale.ticket_number.split('-')[1]) if '-' in last_sale.ticket_number else 0
                self.ticket_number = f"TKT-{last_number + 1:06d}"
            except (ValueError, IndexError):
                self.ticket_number = "TKT-000001"
        else:
            self.ticket_number = "TKT-000001"

    def calculate_totals(self):
        """Calcula los totales de la venta"""
        if not self.pk:
            return  # No calcular si la venta no tiene ID
        
        items = self.items.all()
        self.subtotal = sum(item.subtotal for item in items)
        self.total_discount = sum(item.discount_amount for item in items)
        self.total_final = self.subtotal - self.total_discount

    def cancel_sale(self):
        """Cancela la venta (soft delete)"""
        self.is_active = False
        self.save()


class SaleItem(BaseModel):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_("Sale")
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='sale_items',
        verbose_name=_("Product")
    )
    quantity = models.IntegerField(_("Quantity"))
    unit_price = models.DecimalField(_("Unit Price"), max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percentage = models.DecimalField(_("Discount Percentage"), max_digits=5, decimal_places=2, default=0)
    subtotal = models.DecimalField(_("Subtotal"), max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = _("Sale Item")
        verbose_name_plural = _("Sale Items")

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def save(self, *args, **kwargs):
        # Si no se especifica unit_price, usar el precio del producto
        if self.unit_price is None:
            self.unit_price = self.product.price
        
        # Calcular subtotal
        self.calculate_subtotal()
        
        # Guardar el item
        super().save(*args, **kwargs)
        
        # Recalcular totales de la venta después de guardar
        if self.sale.pk:
            self.sale.calculate_totals()
            self.sale.save(update_fields=['subtotal', 'total_discount', 'total_final'])

    def validate_stock_availability(self):
        """Valida que haya stock suficiente para la venta"""
        from stock.models import Stock
        
        # Verificar que el producto esté activo
        if not self.product.is_active:
            raise ValueError(f"El producto '{self.product.name}' no está activo")
        
        # Verificar que existe un registro de stock
        try:
            stock = Stock.objects.get(product=self.product)
            current_stock = stock.current_quantity
        except Stock.DoesNotExist:
            raise ValueError(f"No hay registro de stock para el producto '{self.product.name}'")
        
        # Verificar stock disponible
        if current_stock <= 0:
            raise ValueError(
                f"No hay stock disponible para '{self.product.name}'. "
                f"Stock actual: {current_stock}"
            )
        
        if current_stock < self.quantity:
            raise ValueError(
                f"Stock insuficiente para '{self.product.name}'. "
                f"Disponible: {current_stock}, Solicitado: {self.quantity}"
            )

    def calculate_subtotal(self):
        """Calcula el subtotal del item"""
        if self.unit_price and self.quantity:
            discount_amount = (self.unit_price * self.quantity * self.discount_percentage) / 100
            self.subtotal = (self.unit_price * self.quantity) - discount_amount
        else:
            self.subtotal = 0

    @property
    def discount_amount(self):
        """Calcula el monto del descuento"""
        if self.unit_price and self.quantity:
            return (self.unit_price * self.quantity * self.discount_percentage) / 100
        return 0
