"""Provedor de mentira para desenvolver e testar o fluxo inteiro sem conta
em nenhum banco. NÃO usar em produção: ninguém paga de verdade."""
import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .base import CobrancaPix, GatewayPix, WebhookInvalido


class GatewaySimulado(GatewayPix):
    nome = 'simulado'

    def criar_cobranca(self, pagamento, cliente, descricao):
        codigo = uuid.uuid4().hex
        return CobrancaPix(
            id_externo=f'sim_{codigo}',
            copia_cola=f'00020126SIMULADO-IFIX-{codigo}-NAO-PAGUE-ISTO6304ABCD',
            qrcode_base64='',
            expira_em=timezone.now() + timedelta(minutes=settings.PIX_EXPIRACAO_MINUTOS),
        )

    def consultar(self, pagamento):
        return 'pendente'

    def repassar(self, pagamento, chave_pix):
        return f'sim_repasse_{uuid.uuid4().hex[:12]}'

    def reembolsar(self, pagamento):
        return None

    def ler_webhook(self, request):
        raise WebhookInvalido('O provedor simulado não recebe webhooks.')
