# Generated by Django 5.1.1 on 2025-06-18 20:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_productimage"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="cost_price",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=10, verbose_name="Cost Price"
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="description",
            field=models.TextField(blank=True, null=True, verbose_name="Description"),
        ),
        migrations.AddField(
            model_name="product",
            name="min_stock",
            field=models.IntegerField(
                default=0,
                help_text="Stock mínimo para alertas",
                verbose_name="Minimum Stock",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="unit",
            field=models.CharField(
                default="unidad",
                help_text="Unidad de medida: unidad, kg, litro, etc.",
                max_length=20,
                verbose_name="Unit",
            ),
        ),
    ]
