from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from products.models import Product
from django_base.base_utils.base_models import BaseModel


class StockMovement(BaseModel):
    MOVEMENT_TYPES = (
        ('ingreso', _('Income')),
        ('egreso', _('Expense')),
    )

    user = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name='stock_movements',
        verbose_name=_("User")
    )
    type = models.CharField(_("Type"), max_length=20, choices=MOVEMENT_TYPES)
    reason = models.CharField(_("Reason"), max_length=255)

    class Meta:
        verbose_name = _("Stock Movement")
        verbose_name_plural = _("Stock Movements")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_type_display()} - {self.created_at}"


class StockMovementItem(BaseModel):
    stock_movement = models.ForeignKey(
        StockMovement,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_("Stock Movement")
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='stock_movement_items',
        verbose_name=_("Product")
    )
    quantity = models.IntegerField(_("Quantity"))
    unit_price = models.DecimalField(_("Unit Price"), max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = _("Stock Movement Item")
        verbose_name_plural = _("Stock Movement Items")

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
