from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django_base.base_utils.base_models import BaseModel
from django.db.models import Sum
from decimal import Decimal


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

    @property
    def is_open(self):
        """Verifica si la caja está abierta"""
        return self.closed_at is None

    @property
    def total_sales(self):
        """Total de ventas activas en esta caja"""
        return self.sales.filter(is_active=True).aggregate(
            total=Sum('total_final')
        )['total'] or Decimal('0.00')

    @property
    def total_movements(self):
        """Total de movimientos de caja"""
        movements = self.movements.all()
        income = movements.filter(type='ingreso').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        expense = movements.filter(type='egreso').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        return income - expense

    def calculate_cash(self):
        """Calcula el efectivo esperado en caja"""
        self.calculated_cash = self.initial_cash + self.total_sales + self.total_movements
        return self.calculated_cash

    def close_cashbox(self, counted_cash, cash_to_keep=None):
        """Cierra la caja y calcula diferencias"""
        if not self.is_open:
            raise ValueError("La caja ya está cerrada")
        
        self.calculate_cash()
        self.counted_cash = counted_cash
        self.difference = self.counted_cash - self.calculated_cash
        self.cash_to_keep = cash_to_keep or self.counted_cash
        self.cash_to_withdraw = self.counted_cash - (cash_to_keep or self.counted_cash)
        self.closed_at = models.timezone.now()
        self.save()

    def get_summary(self):
        """Obtiene resumen de la caja"""
        return {
            'id': self.id,
            'is_open': self.is_open,
            'initial_cash': self.initial_cash,
            'total_sales': self.total_sales,
            'total_movements': self.total_movements,
            'calculated_cash': self.calculate_cash(),
            'counted_cash': self.counted_cash,
            'difference': self.difference,
            'opened_at': self.opened_at,
            'closed_at': self.closed_at,
        }


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

    def save(self, *args, **kwargs):
        # Validar que la caja esté abierta
        if not self.cashbox.is_open:
            raise ValueError("No se pueden hacer movimientos en una caja cerrada")
        super().save(*args, **kwargs)
