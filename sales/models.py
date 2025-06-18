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
    subtotal = models.DecimalField(_("Subtotal"), max_digits=10, decimal_places=2)
    total_discount = models.DecimalField(_("Total Discount"), max_digits=10, decimal_places=2, default=0)
    total_final = models.DecimalField(_("Total Final"), max_digits=10, decimal_places=2)
    payment_method = models.CharField(_("Payment Method"), max_length=20, choices=PAYMENT_METHODS)

    class Meta:
        verbose_name = _("Sale")
        verbose_name_plural = _("Sales")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sale #{self.id} - {self.created_at}"


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
    unit_price = models.DecimalField(_("Unit Price"), max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(_("Discount Percentage"), max_digits=5, decimal_places=2, default=0)
    subtotal = models.DecimalField(_("Subtotal"), max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = _("Sale Item")
        verbose_name_plural = _("Sale Items")

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
