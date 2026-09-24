"""Integração com o Asaas (https://docs.asaas.com) - PENDENTE.

Quando o IFIX tiver CNPJ e conta Asaas, implemente os métodos abaixo (todos
falam com `settings.ASAAS_BASE_URL` usando o header `access_token:
settings.ASAAS_API_KEY`) e mude `IFIX_PIX_PROVEDOR=asaas`.

O que cada método precisa fazer:

criar_cobranca
    1. Criar/reaproveitar o cliente:  POST /customers
       {name, email, cpfCnpj}  -> guarde o id do cliente (o Asaas EXIGE
       CPF/CNPJ: falta coletar no cadastro do cliente).
    2. Criar a cobrança:  POST /payments
       {customer, billingType: "PIX", value, dueDate, description,
        externalReference: str(pagamento.pk)}  -> id_externo = resposta["id"]
    3. Pegar o QR Code:  GET /payments/{id}/pixQrCode
       -> {encodedImage: base64 PNG, payload: copia-e-cola, expirationDate}

consultar
    GET /payments/{id} -> status "RECEIVED"/"CONFIRMED" = pago;
    "PENDING" = pendente; "OVERDUE" = expirado.

repassar  (fim da retenção)
    POST /transfers
    {value: valor_profissional, operationType: "PIX",
     pixAddressKey: chave_pix, pixAddressKeyType: "EVP"/"CPF"/...}
    -> id_repasse = resposta["id"]

reembolsar
    POST /payments/{id}/refund

ler_webhook
    Cadastre em Integrações > Webhooks a URL
    https://SEU-DOMINIO/servicos/webhooks/pix/asaas/ com um token; o Asaas o
    envia no header `asaas-access-token`. Compare com
    settings.ASAAS_WEBHOOK_TOKEN (hmac.compare_digest) e leia o JSON:
    {"event": "PAYMENT_RECEIVED" | "PAYMENT_CONFIRMED", "payment": {"id": ...}}
"""
from .base import GatewayPix, ProvedorNaoConfigurado

MENSAGEM = 'Integração com o Asaas ainda não implementada (veja services/pagamentos/asaas.py).'


class GatewayAsaas(GatewayPix):
    nome = 'asaas'

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
