"""Contrato que todo provedor de Pix precisa cumprir.

O resto do sistema só conhece `GatewayPix`: para trocar de provedor (ou
usar o simulado em testes) basta mudar `PIX_PROVEDOR` em settings - nenhuma
tela nem regra de negócio precisa ser alterada.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class ProvedorNaoConfigurado(Exception):
    """As chaves do provedor não foram preenchidas / integração pendente."""


class WebhookInvalido(Exception):
    """A chamada recebida não veio do provedor (assinatura/token inválidos)."""


@dataclass
class CobrancaPix:
    id_externo: str
    copia_cola: str
    qrcode_base64: str = ''
    expira_em: Optional[datetime] = None


@dataclass
class EventoPagamento:
    id_externo: str
    pago: bool


class GatewayPix:
    nome = 'base'

    def criar_cobranca(self, pagamento, cliente, descricao) -> CobrancaPix:
        """Gera a cobrança Pix (QR Code + copia-e-cola) no provedor."""
        raise NotImplementedError

    def consultar(self, pagamento) -> str:
        """Retorna 'pago', 'pendente' ou 'expirado' (fallback caso o
        webhook atrase)."""
        raise NotImplementedError

    def repassar(self, pagamento, chave_pix) -> str:
        """Envia `pagamento.valor_profissional` para a chave Pix do
        profissional e devolve o id do repasse. É aqui que a retenção
        termina: o dinheiro só sai depois da conclusão do serviço."""
        raise NotImplementedError

    def reembolsar(self, pagamento) -> None:
        """Devolve o valor total ao cliente."""
        raise NotImplementedError

    def ler_webhook(self, request) -> EventoPagamento:
        """Valida a autenticidade da chamada do provedor e devolve o
        evento. Deve levantar WebhookInvalido se não for autêntica."""
        raise NotImplementedError
