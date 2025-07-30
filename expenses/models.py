from django.db import models
from django.utils.translation import gettext_lazy as _
from django_base.base_utils.base_models import BaseSoftDeleteModel, BaseModel
from decimal import Decimal


class ExpenseCategory(BaseSoftDeleteModel):
    """
    Modelo para categorizar los gastos fijos
    """
    name = models.CharField(_("Nombre"), max_length=255)
    description = models.TextField(_("Descripción"), blank=True, null=True)
    is_active = models.BooleanField(_("Activo"), default=True)
    color = models.CharField(_("Color"), max_length=7, default="#007bff", help_text=_("Color en formato hexadecimal"))

    class Meta:
        verbose_name = _("Categoría de Gasto")
        verbose_name_plural = _("Categorías de Gastos")
        ordering = ["name"]

    def __str__(self):
        return self.name


class FixedExpense(BaseModel):
    """
    Modelo para gestionar gastos fijos mensuales
    """
    PAYMENT_STATUS_CHOICES = (
        ('pending', _('Pendiente')),
        ('partial', _('Pago Parcial')),
        ('paid', _('Pagado')),
        ('overdue', _('Vencido')),
    )

    PAYMENT_FREQUENCY_CHOICES = (
        ('monthly', _('Mensual')),
        ('quarterly', _('Trimestral')),
        ('biannual', _('Semestral')),
        ('annual', _('Anual')),
    )

    name = models.CharField(_("Nombre del Gasto"), max_length=255)
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.CASCADE,
        related_name='expenses',
        verbose_name=_("Categoría")
    )
    amount = models.DecimalField(_("Monto"), max_digits=12, decimal_places=2)
    frequency = models.CharField(
        _("Frecuencia"),
        max_length=20,
        choices=PAYMENT_FREQUENCY_CHOICES,
        default='monthly'
    )
    due_day = models.IntegerField(_("Día de Vencimiento"), help_text=_("Día del mes en que vence"))
    description = models.TextField(_("Descripción"), blank=True, null=True)
    is_active = models.BooleanField(_("Activo"), default=True)
    notes = models.TextField(_("Notas"), blank=True, null=True)

    class Meta:
        verbose_name = _("Gasto Fijo")
        verbose_name_plural = _("Gastos Fijos")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - ${self.amount}"

    @property
    def monthly_amount(self):
        """Calcula el monto mensual basado en la frecuencia"""
        if self.frequency == 'monthly':
            return self.amount
        elif self.frequency == 'quarterly':
            return self.amount / 3
        elif self.frequency == 'biannual':
            return self.amount / 6
        elif self.frequency == 'annual':
            return self.amount / 12
        return self.amount

    @property
    def is_up_to_date(self):
        """Verifica si el gasto fijo está al día (sin boletas vencidas sin pagar completamente)"""
        from django.utils import timezone
        today = timezone.now().date()
        
        # Buscar boletas vencidas que no estén completamente pagadas
        overdue_expenses = self.monthly_expenses.filter(
            due_date__lt=today
        ).exclude(
            is_paid=True
        ).exists()
        
        return not overdue_expenses


class MonthlyExpense(BaseModel):
    """
    Modelo para registrar los gastos fijos por mes
    """
    PAYMENT_STATUS_CHOICES = (
        ('pending', _('Pendiente')),
        ('partial', _('Pago Parcial')),
        ('paid', _('Pagado')),
        ('overdue', _('Vencido')),
    )

    fixed_expense = models.ForeignKey(
        FixedExpense,
        on_delete=models.CASCADE,
        related_name='monthly_expenses',
        verbose_name=_("Gasto Fijo")
    )
    year = models.IntegerField(_("Año"))
    month = models.IntegerField(_("Mes"))
    amount = models.DecimalField(_("Monto"), max_digits=12, decimal_places=2)
    due_date = models.DateField(_("Fecha de Vencimiento"))
    payment_status = models.CharField(
        _("Estado de Pago"),
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    is_paid = models.BooleanField(_("Pagado"), default=False)
    notes = models.TextField(_("Notas"), blank=True, null=True)

    class Meta:
        verbose_name = _("Gasto Mensual")
        verbose_name_plural = _("Gastos Mensuales")
        ordering = ["-year", "-month"]
        unique_together = ['fixed_expense', 'year', 'month']

    def __str__(self):
        return f"{self.fixed_expense.name} - {self.month}/{self.year}"

    @property
    def paid_amount(self):
        """Calcula el monto pagado hasta el momento"""
        return sum(payment.amount for payment in self.payments.all())

    @property
    def remaining_amount(self):
        """Calcula el monto restante por pagar"""
        return self.amount - self.paid_amount

    @property
    def is_overdue(self):
        """Verifica si el gasto está vencido"""
        from django.utils import timezone
        return self.due_date < timezone.now().date() and not self.is_paid

    def update_payment_status(self):
        """Actualiza el estado de pago basado en los pagos realizados"""
        paid_amount = self.paid_amount
        
        if paid_amount >= self.amount:
            self.payment_status = 'paid'
            self.is_paid = True
        elif paid_amount > 0:
            self.payment_status = 'partial'
            self.is_paid = False
        elif self.is_overdue:
            self.payment_status = 'overdue'
        else:
            self.payment_status = 'pending'
            self.is_paid = False
        
        self.save()
    
    def get_month_display(self):
        """Retorna el nombre del mes en español"""
        months = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
            7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        return months.get(self.month, '')


class ExpensePayment(BaseModel):
    """
    Modelo para registrar pagos de gastos fijos
    """
    PAYMENT_METHOD_CHOICES = (
        ('cash', _('Efectivo')),
        ('transfer', _('Transferencia')),
        ('check', _('Cheque')),
        ('card', _('Tarjeta')),
        ('automatic', _('Débito Automático')),
        ('other', _('Otro')),
    )

    monthly_expense = models.ForeignKey(
        MonthlyExpense,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name=_("Gasto Mensual")
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
        verbose_name = _("Pago de Gasto")
        verbose_name_plural = _("Pagos de Gastos")
        ordering = ["-payment_date"]

    def __str__(self):
        return f"{self.monthly_expense} - ${self.amount} - {self.payment_date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Actualizar el estado de pago del gasto mensual
        self.monthly_expense.update_payment_status()


class VariableExpense(BaseModel):
    """
    Modelo para gastos variables (no fijos mensuales)
    """
    PAYMENT_STATUS_CHOICES = (
        ('pending', _('Pendiente')),
        ('paid', _('Pagado')),
    )

    PAYMENT_METHOD_CHOICES = (
        ('cash', _('Efectivo')),
        ('transfer', _('Transferencia')),
        ('check', _('Cheque')),
        ('card', _('Tarjeta')),
        ('other', _('Otro')),
    )

    name = models.CharField(_("Nombre del Gasto"), max_length=255)
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.CASCADE,
        related_name='variable_expenses',
        verbose_name=_("Categoría")
    )
    amount = models.DecimalField(_("Monto"), max_digits=12, decimal_places=2)
    expense_date = models.DateField(_("Fecha del Gasto"))
    payment_status = models.CharField(
        _("Estado de Pago"),
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    payment_method = models.CharField(
        _("Método de Pago"),
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
        null=True
    )
    description = models.TextField(_("Descripción"), blank=True, null=True)
    notes = models.TextField(_("Notas"), blank=True, null=True)

    class Meta:
        verbose_name = _("Gasto Variable")
        verbose_name_plural = _("Gastos Variables")
        ordering = ["-expense_date"]

    def __str__(self):
        return f"{self.name} - ${self.amount} - {self.expense_date}"
