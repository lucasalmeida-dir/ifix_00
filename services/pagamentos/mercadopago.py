"""Integração com o Mercado Pago (https://www.mercadopago.com.br/developers)
- PENDENTE.

Implemente quando o IFIX tiver conta e mude `IFIX_PIX_PROVEDOR=mercadopago`.
Todas as chamadas usam `Authorization: Bearer settings.MERCADOPAGO_ACCESS_TOKEN`.

criar_cobranca
    POST /v1/payments  (header X-Idempotency-Key: str(pagamento.pk))
    {transaction_amount, description, payment_method_id: "pix",
     payer: {email}, date_of_expiration, external_reference: str(pk),
     notification_url: "https://SEU-DOMINIO/servicos/webhooks/pix/mercadopago/"}
    -> id_externo = resposta["id"];
       copia_cola = point_of_interaction.transaction_data.qr_code
       qrcode_base64 = point_of_interaction.transaction_data.qr_code_base64

consultar
    GET /v1/payments/{id} -> status "approved" = pago, "pending" = pendente,
    "expired"/"cancelled" = expirado.

repassar  (fim da retenção)
    O Mercado Pago não manda Pix para uma chave qualquer numa conta comum.
    Duas opções: (a) contas de vendedores conectadas por OAuth e
    `application_fee` (marketplace) na cobrança; ou (b) transferência de
    saldo via produto de "Payouts"/Money Out, se disponível na conta. Decida
    junto com o suporte comercial do Mercado Pago.

reembolsar
    POST /v1/payments/{id}/refunds

ler_webhook
    Valide o header `x-signature` (HMAC-SHA256 do manifesto
    "id:{data.id};request-id:{x-request-id};ts:{ts};" com
    settings.MERCADOPAGO_WEBHOOK_SECRET) e, no evento "payment", consulte
    GET /v1/payments/{data.id} para confirmar o status antes de agir.
"""
from .base import GatewayPix, ProvedorNaoConfigurado

MENSAGEM = 'Integração com o Mercado Pago ainda não implementada (veja services/pagamentos/mercadopago.py).'


class GatewayMercadoPago(GatewayPix):
    nome = 'mercadopago'

    def criar_cobranca(self, pagamento, cliente, descricao):
        raise ProvedorNaoConfigurado(MENSAGEM)

    def consultar(self, pagamento):
        raise ProvedorNaoConfigurado(MENSAGEM)

    def repassar(self, pagamento, chave_pix):
        raise ProvedorNaoConfigurado(MENSAGEM)

    def reembolsar(self, pagamento):
        raise ProvedorNaoConfigurado(MENSAGEM)

    def ler_webhook(self, request):
        raise ProvedorNaoConfigurado(MENSAGEM)
