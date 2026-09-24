from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse

import seo

from services.models import Avaliacao


def home(request):
    """Página inicial: mostra opções diferentes para visitante, usuário e profissional."""
    depoimentos = Avaliacao.objects.exclude(comentario='').select_related(
        'profissional', 'usuario', 'solicitacao', 'solicitacao__servico',
    ).order_by('-criado_em')[:9]
    logo = seo.url_absoluta(request, staticfiles_storage.url('css/img/logo.png'))
    return render(request, 'home.html', {
        'depoimentos': depoimentos,
        'json_ld': seo.json_ld(*seo.site_ld(request, logo)),
    })


def privacidade(request):
    """Política de Privacidade (LGPD)."""
    return render(request, 'legal/privacidade.html')


def termos_clientes(request):
    """Termos de Uso para clientes (os profissionais aceitam um termo próprio)."""
    return render(request, 'legal/termos_clientes.html')


def robots_txt(request):
    linhas = [
        'User-agent: *',
        'Disallow: /admin/',
        'Disallow: /conta/',
        'Allow: /conta/cadastro/',
        'Disallow: /media/',
        'Disallow: /servicos/mensagens/',
        'Disallow: /servicos/mapa/',
        'Disallow: /servicos/orcamentos/',
        'Disallow: /servicos/minhas-solicitacoes/',
        'Disallow: /servicos/favoritos/',
        'Disallow: /servicos/*/favoritar/',
        'Disallow: /servicos/profissional/',
        'Disallow: /servicos/solicitacao/',
        'Disallow: /servicos/*/solicitar/',
        'Disallow: /*?q=',
        '',
        f'Sitemap: {seo.url_absoluta(request, reverse("sitemap"))}',
    ]
    return HttpResponse(chr(10).join(linhas), content_type='text/plain; charset=utf-8')
