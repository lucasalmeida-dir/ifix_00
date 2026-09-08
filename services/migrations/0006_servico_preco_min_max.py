# Generated manually: substitui o campo único "preco" por uma faixa
# estimada de preço ("preco_min" / "preco_max") no Serviço.

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0005_avaliacao'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='servico',
            name='preco',
        ),
        migrations.AddField(
            model_name='servico',
            name='preco_min',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, default=0,
                validators=[MinValueValidator(0)],
                verbose_name='Preço estimado a partir de (R$)',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='servico',
            name='preco_max',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, default=0,
                validators=[MinValueValidator(0)],
                verbose_name='Preço estimado até (R$)',
            ),
            preserve_default=False,
        ),
    ]
