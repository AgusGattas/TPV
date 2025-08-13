from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.files.uploadedfile import InMemoryUploadedFile
from django_base.base_utils.base_models import BaseSoftDeleteModel, BaseModel
from django_base.base_utils.base_validators import FileSizeValidator
from django_base.base_utils.utils import reduce_image_quality
import random


class Product(BaseSoftDeleteModel):
    name = models.CharField(_("Name"), max_length=255, db_index=True)
    barcode = models.CharField(_("Barcode"), max_length=50, unique=True, null=True, blank=True, db_index=True)
    price = models.DecimalField(_("Price"), max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(_("Cost Price"), max_digits=10, decimal_places=2, default=0)
    min_stock = models.IntegerField(_("Minimum Stock"), default=0, help_text=_("Stock mínimo para alertas"))
    is_active = models.BooleanField(_("Is Active"), default=True, db_index=True)
    description = models.TextField(_("Description"), blank=True, null=True)
    unit = models.CharField(_("Unit"), max_length=20, default="unidad", help_text=_("Unidad de medida: unidad, kg, litro, etc."))

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ["name"]
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['barcode']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Generar código de barras automáticamente si no existe
        if not self.barcode:
            self.barcode = self.generate_barcode()
        
        super().save(*args, **kwargs)

    def generate_barcode(self):
        """Genera un código de barras único de 13 dígitos"""
        while True:
            # Generar código de 13 dígitos (formato EAN-13)
            barcode = ''.join([str(random.randint(0, 9)) for _ in range(12)])
            
            # Calcular dígito de control (algoritmo EAN-13)
            total = 0
            for i in range(12):
                if i % 2 == 0:
                    total += int(barcode[i])
                else:
                    total += int(barcode[i]) * 3
            
            check_digit = (10 - (total % 10)) % 10
            barcode += str(check_digit)
            
            # Verificar que el código no exista
            if not Product.objects.filter(barcode=barcode).exists():
                return barcode

    @property
    def current_stock(self):
        """Obtiene el stock actual desde el modelo Stock"""
        try:
            return self.stock_info.current_quantity
        except:
            return 0

    @property
    def stock_status(self):
        """Retorna el estado del stock"""
        current_stock = self.current_stock
        if current_stock <= 0:
            return "sin_stock"
        elif current_stock <= self.min_stock:
            return "bajo_stock"
        else:
            return "ok"

    def has_stock_available(self, quantity):
        """Verifica si hay stock suficiente para la cantidad solicitada"""
        return self.current_stock >= quantity

    def get_available_stock(self):
        """Retorna el stock disponible para venta"""
        return max(0, self.current_stock)


class ProductImage(BaseModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name=_("Product"),
    )
    image = models.ImageField(
        upload_to="products",
        null=True,
        blank=True,
        validators=[
            FileSizeValidator(mb_limit=3),
        ],
        verbose_name=_("Image"),
    )

    def __str__(self):
        return f"{self.product} - {self.image}"

    def save(self, *args, **kwargs):
        if self.image:
            image_bytes = self.image.read()
            reduced_image = reduce_image_quality(image_bytes)
            file_name = self.image.name
            content_type = (
                self.image.file.content_type
                if hasattr(self.image.file, "content_type")
                else "image/jpg"
            )
            self.image = InMemoryUploadedFile(
                reduced_image,
                "ImageField",
                file_name,
                content_type,
                reduced_image.tell,
                None,
            )
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Product Image")
        verbose_name_plural = _("Product Images")
