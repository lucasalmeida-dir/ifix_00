from django.db import migrations


CATEGORIAS = [
    ('Hidráulica', 'hidraulica', '🚰'),
    ('Elétrica', 'eletrica', '💡'),
    ('Desentupimento', 'desentupimento', '🪠'),
    ('Marcenaria', 'marcenaria', '🪚'),
    ('Seu problema', 'seu-problema', '🛠️'),
]


def criar_categorias(apps, schema_editor):
    CategoriaServico = apps.get_model('services', 'CategoriaServico')
    for nome, slug, icone in CATEGORIAS:
        CategoriaServico.objects.get_or_create(
            slug=slug,
            defaults={'nome': nome, 'icone': icone},
        )


def remover_categorias(apps, schema_editor):
    CategoriaServico = apps.get_model('services', 'CategoriaServico')
    slugs = [slug for _, slug, _ in CATEGORIAS]
    CategoriaServico.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(criar_categorias, remover_categorias),
    ]
