from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from services.models import CategoriaServico, Servico


class PaginasSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return ['home', 'services:servico_list', 'accounts:register_user', 'accounts:register_professional', 'privacidade', 'termos_clientes']

    def location(self, item):
        return reverse(item)


class CategoriasSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.9

    def items(self):
        return CategoriaServico.objects.all()


class ServicosSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Servico.objects.select_related('categoria').order_by('-atualizado_em')

    def lastmod(self, obj):
        return obj.atualizado_em


class CidadesSitemap(Sitemap):
    """Páginas "Eletricista em Campinas": uma por combinação de categoria +
    cidade que tenha pelo menos um profissional com serviço cadastrado."""
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        pares = Servico.objects.exclude(
            profissional__profile__cidade_slug='',
        ).values_list('categoria__slug', 'profissional__profile__cidade_slug').distinct()
        return sorted(set(pares))

    def location(self, item):
        categoria_slug, cidade_slug = item
        return reverse('services:servico_categoria_cidade', args=[categoria_slug, cidade_slug])
