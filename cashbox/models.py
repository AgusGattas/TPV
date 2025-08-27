from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django_base.base_utils.base_models import BaseModel
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
import decimal


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
    closing_notes = models.TextField(_("Closing Notes"), blank=True, null=True)

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
    def cash_sales(self):
        """Total de ventas en efectivo en esta caja"""
        return self.sales.filter(
            is_active=True,
            payment_method='efectivo'
        ).aggregate(
            total=Sum('total_final')
        )['total'] or Decimal('0.00')

    @property
    def debit_sales(self):
        """Total de ventas con tarjeta de débito en esta caja"""
        return self.sales.filter(
            is_active=True,
            payment_method='debito'
        ).aggregate(
            total=Sum('total_final')
        )['total'] or Decimal('0.00')

    @property
    def credit_sales(self):
        """Total de ventas con tarjeta de crédito en esta caja"""
        return self.sales.filter(
            is_active=True,
            payment_method='credito'
        ).aggregate(
            total=Sum('total_final')
        )['total'] or Decimal('0.00')

    @property
    def transfer_sales(self):
        """Total de ventas por transferencia en esta caja"""
        return self.sales.filter(
            is_active=True,
            payment_method='transferencia'
        ).aggregate(
            total=Sum('total_final')
        )['total'] or Decimal('0.00')

    @property
    def qr_sales(self):
        """Total de ventas por QR en esta caja"""
        return self.sales.filter(
            is_active=True,
            payment_method='qr'
        ).aggregate(
            total=Sum('total_final')
        )['total'] or Decimal('0.00')

    @property
    def sales_by_payment_method(self):
        """Diccionario con ventas agrupadas por método de pago"""
        return {
            'efectivo': self.cash_sales,
            'debito': self.debit_sales,
            'credito': self.credit_sales,
            'transferencia': self.transfer_sales,
            'qr': self.qr_sales,
        }

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

    @property
    def total_income(self):
        """Total de ingresos (ventas + movimientos de ingreso)"""
        sales_income = self.total_sales
        movement_income = self.movements.filter(type='ingreso').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        return sales_income + movement_income

    @property
    def total_expenses(self):
        """Total de egresos (movimientos de egreso)"""
        return self.movements.filter(type='egreso').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

    @property
    def movements_income(self):
        """Total de ingresos por movimientos (sin incluir ventas)"""
        return self.movements.filter(type='ingreso').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

    @property
    def current_balance(self):
        """Balance actual de la caja"""
        return self.initial_cash + self.total_income - self.total_expenses

    @property
    def average_sale(self):
        """Promedio por venta"""
        sales_count = self.sales.filter(is_active=True).count()
        if sales_count > 0:
            return self.total_sales / sales_count
        return Decimal('0.00')

    @property
    def current_duration_hours(self):
        """Duración actual en horas"""
        if self.closed_at:
            duration = self.closed_at - self.opened_at
        else:
            duration = timezone.now() - self.opened_at
        return int(duration.total_seconds() // 3600)

    @property
    def current_duration_minutes(self):
        """Duración actual en minutos (resto)"""
        if self.closed_at:
            duration = self.closed_at - self.opened_at
        else:
            duration = timezone.now() - self.opened_at
        return int((duration.total_seconds() % 3600) // 60)

    @property
    def duration_hours(self):
        """Duración total en horas (para cajas cerradas)"""
        if self.closed_at:
            duration = self.closed_at - self.opened_at
            return int(duration.total_seconds() // 3600)
        return self.current_duration_hours

    @property
    def duration_minutes(self):
        """Duración total en minutos (para cajas cerradas)"""
        if self.closed_at:
            duration = self.closed_at - self.opened_at
            return int((duration.total_seconds() % 3600) // 60)
        return self.current_duration_minutes

    def calculate_cash(self):
        """Calcula el efectivo esperado en caja"""
        calculated = self.initial_cash + self.cash_sales + self.total_movements
        
        # Asegurar que el resultado sea Decimal
        if not isinstance(calculated, Decimal):
            calculated = Decimal('0.00')
        
        self.calculated_cash = calculated
        return calculated
    
    @property
    def calculate_cash_property(self):
        """Propiedad que calcula el efectivo esperado en caja"""
        if self.calculated_cash is not None:
            return self.calculated_cash
        return self.calculate_cash()

    @classmethod
    def get_last_cash_to_keep(cls):
        """Obtiene el cash_to_keep de la última caja cerrada"""
        last_closed_cashbox = cls.objects.filter(
            closed_at__isnull=False
        ).order_by('-closed_at').first()
        
        if last_closed_cashbox and last_closed_cashbox.cash_to_keep:
            return last_closed_cashbox.cash_to_keep
        return Decimal('0.00')

    @classmethod
    def get_suggested_initial_cash(cls):
        """Obtiene el cash_to_keep sugerido para la nueva caja"""
        return cls.get_last_cash_to_keep()

    def close_cashbox(self, counted_cash, cash_to_keep=None, closing_notes=None):
        """Cierra la caja y calcula diferencias"""
        if not self.is_open:
            raise ValueError("La caja ya está cerrada")
        
        # Convertir counted_cash a Decimal de forma segura
        if isinstance(counted_cash, str):
            counted_cash = counted_cash.replace(',', '.')
        counted_cash = Decimal(str(counted_cash))
        
        # Calcular el efectivo esperado
        calculated_cash = self.calculate_cash()
        
        # Asegurar que calculated_cash sea Decimal
        if not isinstance(calculated_cash, Decimal):
            calculated_cash = Decimal('0.00')
        
        self.counted_cash = counted_cash
        self.calculated_cash = calculated_cash
        self.difference = counted_cash - calculated_cash
        
        # Si no se especifica cash_to_keep, usar el counted_cash completo
        if cash_to_keep is None:
            cash_to_keep = counted_cash
        else:
            if isinstance(cash_to_keep, str):
                cash_to_keep = cash_to_keep.replace(',', '.')
            cash_to_keep = Decimal(str(cash_to_keep))
        
        self.cash_to_keep = cash_to_keep
        self.cash_to_withdraw = counted_cash - cash_to_keep
        self.closing_notes = closing_notes
        self.closed_at = timezone.now()
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
            'cash_to_keep': self.cash_to_keep,
            'cash_to_withdraw': self.cash_to_withdraw,
            'opened_at': self.opened_at,
            'closed_at': self.closed_at,
        }

    def save(self, *args, **kwargs):
        # Validar que no haya cajas abiertas al crear una nueva
        if not self.pk and self.closed_at is None:  # Nueva caja abierta
            if CashBox.objects.filter(closed_at__isnull=True).exists():
                raise ValueError("No se puede abrir una nueva caja mientras haya una caja abierta")
        
        super().save(*args, **kwargs)


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
