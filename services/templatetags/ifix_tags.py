"""Tags de template próprias do IFIX.

`ifix_querystring` faz o mesmo que a tag `{% querystring %}` do Django 5.1+,
mas funciona em qualquer versão do Django (o servidor de produção usa o
Django 4.2, que não tem a tag nativa).
"""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def ifix_querystring(context, **kwargs):
    """Devolve "?a=1&b=2": a query string atual da página com os parâmetros
    informados trocados. Valor None remove o parâmetro.

    Ex.: {% ifix_querystring ordenar='preco' %}  ou  {% ifix_querystring ordenar=None %}
    """
    request = context['request']
    parametros = request.GET.copy()
    for chave, valor in kwargs.items():
        if valor is None:
            parametros.pop(chave, None)
        elif isinstance(valor, (list, tuple)):
            parametros.setlist(chave, [str(v) for v in valor])
        else:
            parametros[chave] = str(valor)
    return '?' + parametros.urlencode() if parametros else '?'
