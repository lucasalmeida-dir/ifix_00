# Remove a categoria "Seu problema" (não faz mais parte das opções
# do painel do profissional). Se algum serviço já estiver cadastrado
# nessa categoria, ele é reatribuído para a primeira categoria
# restante, para não perder o serviço.

from django.db import migrations
from django.db.models import Q


def remover_seu_problema(apps, schema_editor):
    CategoriaServico = apps.get_model('services', 'CategoriaServico')
    Servico = apps.get_model('services', 'Servico')

    categorias = CategoriaServico.objects.filter(
        Q(slug__istartswith='seu-problema') | Q(nome__iexact='seu problema')
    )
    if not categorias.exists():
        return

    outra_categoria = CategoriaServico.objects.exclude(
        Q(slug__istartswith='seu-problema') | Q(nome__iexact='seu problema')
    ).first()

    for categoria in categorias:
        if outra_categoria:
            Servico.objects.filter(categoria=categoria).update(categoria=outra_categoria)
        categoria.delete()


def recriar_seu_problema(apps, schema_editor):
    CategoriaServico = apps.get_model('services', 'CategoriaServico')
    CategoriaServico.objects.get_or_create(
        slug='seu-problema',
        defaults={'nome': 'Seu problema', 'icone': '🛠️'},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0006_servico_preco_min_max'),
    ]

    operations = [
        migrations.RunPython(remover_seu_problema, recriar_seu_problema),
    ]
