# Renomeia a categoria "Desentupimento" para "Pintura" (o site trocou essa
# opção de área de atuação). A categoria é RENOMEADA no lugar (mesmo
# registro, mesmo PK) em vez de apagada e recriada — assim, qualquer
# serviço que já estivesse cadastrado como "Desentupimento" passa a
# aparecer como "Pintura" automaticamente, sem perder nada e sem violar a
# proteção categoria__on_delete=PROTECT em Servico.

from django.db import migrations
from django.db.models import Q


def renomear_para_pintura(apps, schema_editor):
    CategoriaServico = apps.get_model('services', 'CategoriaServico')
    Servico = apps.get_model('services', 'Servico')

    desentupimento = CategoriaServico.objects.filter(
        Q(slug__iexact='desentupimento') | Q(nome__iexact='desentupimento')
    ).first()
    pintura = CategoriaServico.objects.filter(slug__iexact='pintura').first()

    if desentupimento and pintura and desentupimento.pk != pintura.pk:
        # Já existem as duas categorias por algum motivo: junta os
        # serviços em "Pintura" e remove a duplicata de "Desentupimento".
        Servico.objects.filter(categoria=desentupimento).update(categoria=pintura)
        desentupimento.delete()
        return

    if desentupimento:
        desentupimento.nome = 'Pintura'
        desentupimento.slug = 'pintura'
        desentupimento.icone = '🎨'
        desentupimento.save(update_fields=['nome', 'slug', 'icone'])
        return

    # Não havia "Desentupimento" (ex.: banco novo criado já sem ela):
    # garante que "Pintura" existe mesmo assim.
    CategoriaServico.objects.get_or_create(
        slug='pintura', defaults={'nome': 'Pintura', 'icone': '🎨'},
    )


def renomear_para_desentupimento(apps, schema_editor):
    CategoriaServico = apps.get_model('services', 'CategoriaServico')
    pintura = CategoriaServico.objects.filter(slug__iexact='pintura').first()
    if pintura:
        pintura.nome = 'Desentupimento'
        pintura.slug = 'desentupimento'
        pintura.icone = '🪠'
        pintura.save(update_fields=['nome', 'slug', 'icone'])


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0007_remover_categoria_seu_problema'),
    ]

    operations = [
        migrations.RunPython(renomear_para_pintura, renomear_para_desentupimento),
    ]
