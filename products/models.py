from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.files.uploadedfile import InMemoryUploadedFile
from django_base.base_utils.base_models import BaseSoftDeleteModel, BaseModel
from django_base.base_utils.base_validators import FileSizeValidator
from django_base.base_utils.utils import reduce_image_quality


class Product(BaseSoftDeleteModel):
    name = models.CharField(_("Name"), max_length=255)
    barcode = models.CharField(_("Barcode"), max_length=50, unique=True, null=True, blank=True)
    price = models.DecimalField(_("Price"), max_digits=10, decimal_places=2)
    stock = models.IntegerField(_("Stock"), default=0)
    is_active = models.BooleanField(_("Is Active"), default=True)

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ["name"]

    def __str__(self):
        return self.name


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
