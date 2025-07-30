from django.db import models
from django.utils.translation import gettext_lazy as _
from django_base.base_utils.base_models import BaseSoftDeleteModel, BaseModel
from decimal import Decimal


class Supplier(BaseSoftDeleteModel):
    """
    Modelo para gestionar proveedores
    """
    name = models.CharField(_("Nombre"), max_length=255)
    cuit = models.CharField(_("CUIT"), max_length=20, blank=True, null=True)
    email = models.EmailField(_("Email"), blank=True, null=True)
    phone = models.CharField(_("Teléfono"), max_length=20, blank=True, null=True)
    address = models.TextField(_("Dirección"), blank=True, null=True)
    contact_person = models.CharField(_("Persona de contacto"), max_length=255, blank=True, null=True)
    is_active = models.BooleanField(_("Activo"), default=True)
    notes = models.TextField(_("Notas"), blank=True, null=True)

    class Meta:
        verbose_name = _("Proveedor")
        verbose_name_plural = _("Proveedores")
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def total_pending_amount(self):
        """Calcula el monto total pendiente de pago"""
        return sum(
            invoice.remaining_amount 
            for invoice in self.invoices.filter(is_paid=False)
        )

    @property
    def total_paid_amount(self):
        """Calcula el monto total pagado"""
        return sum(
            invoice.total_amount 
            for invoice in self.invoices.filter(is_paid=True)
        )

    @property
    def is_up_to_date(self):
        """Verifica si el proveedor está al día (sin facturas vencidas sin pagar completamente)"""
        from django.utils import timezone
        today = timezone.now().date()
        
        # Buscar facturas vencidas que no estén completamente pagadas
        overdue_invoices = self.invoices.filter(
            due_date__lt=today
        ).exclude(
            is_paid=True
        ).exists()
        
        return not overdue_invoices


class SupplierInvoice(BaseModel):
    """
    Modelo para gestionar facturas de proveedores
    """
    PAYMENT_STATUS_CHOICES = (
        ('pending', _('Pendiente')),
        ('partial', _('Pago Parcial')),
        ('paid', _('Pagado')),
        ('overdue', _('Vencido')),
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name=_("Proveedor")
    )
    invoice_number = models.CharField(_("Número de Factura"), max_length=50)
    invoice_date = models.DateField(_("Fecha de Factura"))
    due_date = models.DateField(_("Fecha de Vencimiento"))
    total_amount = models.DecimalField(_("Monto Total"), max_digits=12, decimal_places=2)
    description = models.TextField(_("Descripción"), blank=True, null=True)
    payment_status = models.CharField(
        _("Estado de Pago"),
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    is_paid = models.BooleanField(_("Pagado"), default=False)
    notes = models.TextField(_("Notas"), blank=True, null=True)

    class Meta:
        verbose_name = _("Factura de Proveedor")
        verbose_name_plural = _("Facturas de Proveedores")
        ordering = ["-invoice_date"]
        unique_together = ['supplier', 'invoice_number']

    def __str__(self):
        return f"{self.supplier.name} - {self.invoice_number}"

    @property
    def paid_amount(self):
        """Calcula el monto pagado hasta el momento"""
        return sum(payment.amount for payment in self.payments.all())

    @property
    def remaining_amount(self):
        """Calcula el monto restante por pagar"""
        return self.total_amount - self.paid_amount

    @property
    def is_overdue(self):
        """Verifica si la factura está vencida"""
        from django.utils import timezone
        return self.due_date < timezone.now().date() and not self.is_paid

    def update_payment_status(self):
        """Actualiza el estado de pago basado en los pagos realizados"""
        paid_amount = self.paid_amount
        
        if paid_amount >= self.total_amount:
            self.payment_status = 'paid'
            self.is_paid = True
        elif paid_amount > 0:
            self.payment_status = 'partial'
            self.is_paid = False
        elif self.is_overdue:
            self.payment_status = 'overdue'
            self.is_paid = False
        else:
            self.payment_status = 'pending'
            self.is_paid = False
        
        self.save()


class SupplierPayment(BaseModel):
    """
    Modelo para registrar pagos a facturas de proveedores
    """
    PAYMENT_METHOD_CHOICES = (
        ('cash', _('Efectivo')),
        ('transfer', _('Transferencia')),
        ('check', _('Cheque')),
        ('card', _('Tarjeta')),
        ('other', _('Otro')),
    )

    invoice = models.ForeignKey(
        SupplierInvoice,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name=_("Factura")
    )
    amount = models.DecimalField(_("Monto"), max_digits=12, decimal_places=2)
    payment_date = models.DateField(_("Fecha de Pago"))
    payment_method = models.CharField(
        _("Método de Pago"),
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='transfer'
    )
    reference = models.CharField(_("Referencia"), max_length=100, blank=True, null=True)
    notes = models.TextField(_("Notas"), blank=True, null=True)

    class Meta:
        verbose_name = _("Pago a Proveedor")
        verbose_name_plural = _("Pagos a Proveedores")
        ordering = ["-payment_date"]

    def __str__(self):
        return f"{self.invoice} - ${self.amount} - {self.payment_date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Actualizar el estado de pago de la factura
        self.invoice.update_payment_status()
