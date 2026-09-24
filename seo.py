"""Utilitários de SEO: dados estruturados (JSON-LD) e URLs absolutas."""
import json

from django.utils.safestring import mark_safe

NOME_SITE = 'IFIX'
DESCRICAO_PADRAO = (
    'IFIX conecta você a eletricistas, encanadores, marceneiros e pintores '
    'avaliados perto de casa. Compare o preço da visita, agende pelo celular '
    'e feche o serviço com segurança.'
)


def url_absoluta(request, caminho):
    return f'{request.scheme}://{request.get_host()}{caminho}'


def json_ld(*blocos):
    """Serializa um ou mais objetos schema.org para uma tag <script
    type="application/ld+json">, escapando < > & para que o conteúdo
    nunca consiga fechar a tag."""
    dados = blocos[0] if len(blocos) == 1 else list(blocos)
    texto = json.dumps(dados, ensure_ascii=False)
    texto = texto.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return mark_safe(texto)


def breadcrumb_ld(request, itens):
    """itens: lista de (nome, caminho)."""
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {
                '@type': 'ListItem',
                'position': posicao,
                'name': nome,
                'item': url_absoluta(request, caminho),
            }
            for posicao, (nome, caminho) in enumerate(itens, start=1)
        ],
    }


def site_ld(request, logo_url):
    raiz = url_absoluta(request, '/')
    return [
        {
            '@context': 'https://schema.org',
            '@type': 'Organization',
            'name': NOME_SITE,
            'url': raiz,
            'logo': logo_url,
            'description': DESCRICAO_PADRAO,
        },
        {
            '@context': 'https://schema.org',
            '@type': 'WebSite',
            'name': NOME_SITE,
            'url': raiz,
            'inLanguage': 'pt-BR',
            'potentialAction': {
                '@type': 'SearchAction',
                'target': f'{raiz}servicos/?q={{search_term_string}}',
                'query-input': 'required name=search_term_string',
            },
        },
    ]


def servico_ld(request, servico):
    nome_prof = servico.profissional.get_full_name() or servico.profissional.username
    nome = servico.nome + (f' - {servico.subservico}' if servico.subservico else '')
    dados = {
        '@context': 'https://schema.org',
        '@type': 'Service',
        'name': nome,
        'description': servico.descricao,
        'serviceType': servico.categoria.nome,
        'url': url_absoluta(request, servico.get_absolute_url()),
        'provider': {'@type': 'Person', 'name': nome_prof},
        'areaServed': {'@type': 'Country', 'name': 'Brasil'},
        'offers': {
            '@type': 'AggregateOffer',
            'priceCurrency': 'BRL',
            'lowPrice': str(servico.preco_min),
            'highPrice': str(servico.preco_max),
        },
    }
    if getattr(servico, 'total_avaliacoes', 0):
        dados['aggregateRating'] = {
            '@type': 'AggregateRating',
            'ratingValue': round(float(servico.avaliacao_media), 1),
            'reviewCount': servico.total_avaliacoes,
            'bestRating': 5,
            'worstRating': 1,
        }
    return dados
