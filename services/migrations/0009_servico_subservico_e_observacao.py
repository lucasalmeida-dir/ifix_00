# Generated manually: adiciona o campo "Subserviço" ao Serviço e renomeia
# o rótulo (verbose_name) do campo "descricao" para "Observação" — o nome
# da coluna no banco continua sendo "descricao" para não quebrar código e
# templates existentes que já leem `servico.descricao`.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0008_renomear_desentupimento_para_pintura'),
    ]

    operations = [
        migrations.AddField(
            model_name='servico',
            name='subservico',
            field=models.CharField(blank=True, max_length=150, verbose_name='Subserviço'),
        ),
        migrations.AlterField(
            model_name='servico',
            name='descricao',
            field=models.TextField(verbose_name='Observação'),
        ),
    ]
