from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django_base.base_utils.base_models import BaseModel


class CashBox(BaseModel):
    user = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name='opened_cashboxes',
        verbose_name=_("User")
    )
    opened_at = models.DateTimeField(_("Opened At"), auto_now_add=True)
    initial_cash = models.DecimalField(_("Initial Cash"), max_digits=10, decimal_places=2)
    closed_at = models.DateTimeField(_("Closed At"), null=True, blank=True)
    calculated_cash = models.DecimalField(_("Calculated Cash"), max_digits=10, decimal_places=2, null=True, blank=True)
    counted_cash = models.DecimalField(_("Counted Cash"), max_digits=10, decimal_places=2, null=True, blank=True)
    difference = models.DecimalField(_("Difference"), max_digits=10, decimal_places=2, null=True, blank=True)
    cash_to_keep = models.DecimalField(_("Cash To Keep"), max_digits=10, decimal_places=2, null=True, blank=True)
    cash_to_withdraw = models.DecimalField(_("Cash To Withdraw"), max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = _("Cash Box")
        verbose_name_plural = _("Cash Boxes")
        ordering = ["-opened_at"]

    def __str__(self):
        return f"Cash Box #{self.id} - {self.opened_at}"


class CashMovement(BaseModel):
    MOVEMENT_TYPES = (
        ('ingreso', _('Income')),
        ('egreso', _('Expense')),
    )

    cashbox = models.ForeignKey(
        CashBox,
        on_delete=models.PROTECT,
        related_name='movements',
        verbose_name=_("Cash Box")
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name='cash_movements',
        verbose_name=_("User")
    )
    type = models.CharField(_("Type"), max_length=20, choices=MOVEMENT_TYPES)
    amount = models.DecimalField(_("Amount"), max_digits=10, decimal_places=2)
    reason = models.CharField(_("Reason"), max_length=255)

    class Meta:
        verbose_name = _("Cash Movement")
        verbose_name_plural = _("Cash Movements")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_type_display()} - {self.amount} - {self.created_at}"
