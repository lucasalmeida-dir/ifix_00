"""Dados da página pública do profissional."""
from statistics import median

from .models import SolicitacaoServico

MINIMO_RESPOSTAS = 3
AMOSTRA = 30


def _formatar(segundos):
    minutos = max(1, round(segundos / 60))
    if minutos < 60:
        return f'cerca de {minutos} min'
    horas = round(minutos / 60)
    if horas < 24:
        return f'cerca de {horas} h'
    dias = round(horas / 24)
    return f'cerca de {dias} dia{"s" if dias != 1 else ""}'


def tempo_resposta(profissional):
    """Tempo típico (mediana das últimas respostas) entre o pedido chegar e o
    profissional aceitar/recusar. Devolve None enquanto houver poucas
    respostas para uma média confiável."""
    respondidas = (
        SolicitacaoServico.objects
        .filter(servico__profissional=profissional, respondida_em__isnull=False)
        .order_by('-respondida_em')
        .values_list('criado_em', 'respondida_em')[:AMOSTRA]
    )
    duracoes = [(fim - inicio).total_seconds() for inicio, fim in respondidas]
    if len(duracoes) < MINIMO_RESPOSTAS:
        return None
    return _formatar(median(duracoes))
