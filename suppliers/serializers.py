from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import Supplier, SupplierInvoice, SupplierPayment


class SupplierSerializer(serializers.ModelSerializer):
    total_pending_amount = serializers.ReadOnlyField()
    total_paid_amount = serializers.ReadOnlyField()
    invoices_count = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'cuit', 'email', 'phone', 'address', 
            'contact_person', 'is_active', 'notes', 'created_at',
            'total_pending_amount', 'total_paid_amount', 'invoices_count'
        ]

    def get_invoices_count(self, obj):
        return obj.invoices.count()


class SupplierInvoiceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    paid_amount = serializers.ReadOnlyField()
    remaining_amount = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    payments_count = serializers.SerializerMethodField()

    class Meta:
        model = SupplierInvoice
        fields = [
            'id', 'supplier', 'supplier_name', 'invoice_number', 
            'invoice_date', 'due_date', 'total_amount', 'description',
            'payment_status', 'is_paid', 'notes', 'created_at',
            'paid_amount', 'remaining_amount', 'is_overdue', 'payments_count'
        ]

    def get_payments_count(self, obj):
        return obj.payments.count()


class SupplierPaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    supplier_name = serializers.CharField(source='invoice.supplier.name', read_only=True)

    class Meta:
        model = SupplierPayment
        fields = [
            'id', 'invoice', 'invoice_number', 'supplier_name', 'amount',
            'payment_date', 'payment_method', 'reference', 'notes', 'created_at'
        ]

    def validate(self, data):
        invoice = data.get('invoice')
        amount = data.get('amount')
        
        if invoice and amount:
            # Verificar que el monto no exceda lo que falta pagar
            remaining = invoice.remaining_amount
            if amount > remaining:
                raise serializers.ValidationError(
                    _("El monto del pago no puede exceder el monto restante por pagar")
                )
        
        return data


class SupplierInvoiceDetailSerializer(SupplierInvoiceSerializer):
    payments = SupplierPaymentSerializer(many=True, read_only=True)

    class Meta(SupplierInvoiceSerializer.Meta):
        fields = SupplierInvoiceSerializer.Meta.fields + ['payments']


class SupplierDetailSerializer(SupplierSerializer):
    invoices = SupplierInvoiceSerializer(many=True, read_only=True)

    class Meta(SupplierSerializer.Meta):
        fields = SupplierSerializer.Meta.fields + ['invoices'] 