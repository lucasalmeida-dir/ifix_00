"""Pagamento do orçamento por Pix, com retenção até a conclusão do serviço.

Fluxo:
    cliente aprova o orçamento
      -> iniciar_pagamento()      gera o Pix (QR Code / copia-e-cola)
      -> confirmar_pagamento()    provedor avisou que foi pago: dinheiro RETIDO
      -> cliente marca "serviço concluído"
      -> liberar_pagamento()      repassa ao profissional (menos a comissão)
    (ou, em caso de problema)
      -> reembolsar_pagamento()   devolve tudo ao cliente

A conversa com cada provedor fica em base.py / simulado.py / asaas.py /
mercadopago.py; aqui só existem as regras do IFIX.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import Orcamento, Pagamento
from .base import CobrancaPix, EventoPagamento, GatewayPix, ProvedorNaoConfigurado, WebhookInvalido  # noqa: F401


class PagamentoIndisponivel(Exception):
    """O pagamento não pode ser feito agora (mensagem pronta para o usuário)."""


def habilitado():
    return bool(getattr(settings, 'PIX_HABILITADO', False))


def obter_gateway(nome=None):
    nome = nome or getattr(settings, 'PIX_PROVEDOR', 'simulado')
    if nome == 'asaas':
        from .asaas import GatewayAsaas
        return GatewayAsaas()
    if nome == 'mercadopago':
        from .mercadopago import GatewayMercadoPago
        return GatewayMercadoPago()
    from .simulado import GatewaySimulado
    return GatewaySimulado()


def calcular_valores(valor_total, percentual=None):
    """(comissão, repasse ao profissional), com arredondamento de centavos."""
    percentual = Decimal(str(percentual if percentual is not None else settings.IFIX_COMISSAO_PERCENTUAL))
    valor_total = Decimal(valor_total)
    comissao = (valor_total * percentual / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return comissao, valor_total - comissao


def pagamento_ativo(solicitacao):
    """Pagamento em aberto (aguardando ou retido) ou já repassado."""
    return solicitacao.pagamentos.exclude(
        status__in=[Pagamento.STATUS_REEMBOLSADO, Pagamento.STATUS_EXPIRADO],
    ).first()


@transaction.atomic
def iniciar_pagamento(solicitacao):
    if not habilitado():
        raise PagamentoIndisponivel('O pagamento pelo app ainda não está disponível.')
    orcamento = getattr(solicitacao, 'orcamento', None)
    if not orcamento or orcamento.status != Orcamento.STATUS_APROVADO:
        raise PagamentoIndisponivel('Aprove o orçamento antes de pagar.')
    existente = pagamento_ativo(solicitacao)
    if existente:
        return existente
    if orcamento.valor <= 0:
        raise PagamentoIndisponivel('O orçamento não tem valor a pagar.')

    comissao, repasse = calcular_valores(orcamento.valor)
    gateway = obter_gateway()
    pagamento = Pagamento(
        solicitacao=solicitacao, orcamento=orcamento, provedor=gateway.nome,
        valor_total=orcamento.valor, comissao_percentual=settings.IFIX_COMISSAO_PERCENTUAL,
        valor_comissao=comissao, valor_profissional=repasse,
    )
    pagamento.save()
    try:
        cobranca = gateway.criar_cobranca(
            pagamento, solicitacao.usuario, f'IFIX - {solicitacao.servico.nome}',
        )
    except ProvedorNaoConfigurado as exc:
        raise PagamentoIndisponivel(str(exc))
    pagamento.id_externo = cobranca.id_externo
    pagamento.pix_copia_cola = cobranca.copia_cola
    pagamento.pix_qrcode_base64 = cobranca.qrcode_base64
    pagamento.expira_em = cobranca.expira_em
    pagamento.save()
    return pagamento


@transaction.atomic
def confirmar_pagamento(pagamento):
    """O Pix foi pago: o valor fica retido. Idempotente."""
    pagamento = Pagamento.objects.select_for_update().get(pk=pagamento.pk)
    if pagamento.status != Pagamento.STATUS_PENDENTE:
        return pagamento
    pagamento.status = Pagamento.STATUS_RETIDO
    pagamento.pago_em = timezone.now()
    pagamento.save(update_fields=['status', 'pago_em'])

    from ..notificacoes import notificar, nome_de
    solicitacao = pagamento.solicitacao
    url = f'/servicos/solicitacao/{solicitacao.pk}/pagamento/'
    notificar(
        solicitacao.servico.profissional, 'Pagamento recebido pelo IFIX',
        f'{nome_de(solicitacao.usuario)} pagou R$ {pagamento.valor_total}. O valor fica retido e é '
        'repassado quando o cliente confirmar que o serviço foi concluído.',
        url=url, tipo='pagamento', chave=f'pagamento-pago-{pagamento.pk}',
    )
    notificar(
        solicitacao.usuario, 'Pagamento confirmado',
        'Seu Pix foi recebido. O valor só é repassado ao profissional quando você marcar o serviço como concluído.',
        url=url, tipo='pagamento', chave=f'pagamento-confirmado-{pagamento.pk}',
    )
    return pagamento


@transaction.atomic
def liberar_pagamento(pagamento):
    """Serviço concluído: repassa ao profissional. Idempotente."""
    pagamento = Pagamento.objects.select_for_update().get(pk=pagamento.pk)
    if pagamento.status != Pagamento.STATUS_RETIDO:
        return pagamento
    profissional = pagamento.solicitacao.servico.profissional
    chave = getattr(getattr(profissional, 'profile', None), 'chave_pix', '')
    if not chave:
        raise PagamentoIndisponivel(
            'O profissional ainda não cadastrou a chave Pix para receber - o repasse fica pendente.',
        )
    pagamento.id_repasse = obter_gateway(pagamento.provedor).repassar(pagamento, chave)
    pagamento.status = Pagamento.STATUS_LIBERADO
    pagamento.liberado_em = timezone.now()
    pagamento.save(update_fields=['status', 'id_repasse', 'liberado_em'])

    from ..notificacoes import notificar
    notificar(
        profissional, 'Repasse enviado',
        f'R$ {pagamento.valor_profissional} foram enviados para a sua chave Pix '
        f'(comissão IFIX: R$ {pagamento.valor_comissao}).',
        url=f'/servicos/solicitacao/{pagamento.solicitacao_id}/pagamento/', tipo='pagamento',
        chave=f'pagamento-liberado-{pagamento.pk}',
    )
    return pagamento


@transaction.atomic
def reembolsar_pagamento(pagamento):
    """Devolve o valor total ao cliente (usado pelo suporte, no admin)."""
    pagamento = Pagamento.objects.select_for_update().get(pk=pagamento.pk)
    if pagamento.status != Pagamento.STATUS_RETIDO:
        return pagamento
    obter_gateway(pagamento.provedor).reembolsar(pagamento)
    pagamento.status = Pagamento.STATUS_REEMBOLSADO
    pagamento.reembolsado_em = timezone.now()
    pagamento.save(update_fields=['status', 'reembolsado_em'])

    from ..notificacoes import notificar
    notificar(
        pagamento.solicitacao.usuario, 'Pagamento reembolsado',
        f'R$ {pagamento.valor_total} foram devolvidos ao seu Pix.',
        url=f'/servicos/solicitacao/{pagamento.solicitacao_id}/pagamento/', tipo='pagamento',
        chave=f'pagamento-reembolso-{pagamento.pk}',
    )
    return pagamento
