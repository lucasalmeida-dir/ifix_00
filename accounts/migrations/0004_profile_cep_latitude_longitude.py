# Generated manually - adiciona CEP e coordenadas ao Profile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_profile_foto'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='cep',
            field=models.CharField(blank=True, max_length=9, verbose_name='CEP'),
        ),
        migrations.AddField(
            model_name='profile',
            name='latitude',
            field=models.FloatField(blank=True, null=True, verbose_name='Latitude'),
        ),
        migrations.AddField(
            model_name='profile',
            name='longitude',
            field=models.FloatField(blank=True, null=True, verbose_name='Longitude'),
        ),
    ]
