"""Central de avisos do IFIX.

Tudo que precisa avisar alguém (novo pedido, orçamento, "a caminho",
lembrete...) passa por `notificar()`. Hoje ele grava a notificação que
aparece no sino da navbar e manda um e-mail; quando houver push ou
WhatsApp, é só acrescentar o canal AQUI - nenhuma outra parte do sistema
precisa mudar.
"""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from .models import (
    Notificacao, PropostaReagendamento, SolicitacaoServico,
)
from . import regras


def notificar(usuario, titulo, texto='', url='', tipo='geral', chave='', email=True):
    """Cria o aviso (uma vez só, se `chave` for informada) e envia o e-mail."""
    if chave and Notificacao.objects.filter(usuario=usuario, chave=chave).exists():
        return None
    notificacao = Notificacao.objects.create(
        usuario=usuario, titulo=titulo[:120], texto=texto[:255], url=url[:255], tipo=tipo, chave=chave,
    )
    if email and usuario.email:
        corpo = texto or titulo
        send_mail(
            f'IFIX - {titulo}', corpo, settings.DEFAULT_FROM_EMAIL, [usuario.email], fail_silently=True,
        )
    return notificacao


def nome_de(usuario):
    return usuario.get_full_name() or usuario.username


# ---------------------------------------------------------------- lembretes

def gerar_lembretes(usuario=None):
    """Cria os lembretes "amanhã" e "hoje" das visitas agendadas.

    Idempotente: cada lembrete tem uma chave própria, então rodar várias
    vezes não duplica. É chamado quando o usuário abre o site e também pelo
    comando `python manage.py enviar_lembretes` (para agendar em cron e
    avisar quem não entrou no site)."""
    hoje = timezone.localdate()
    amanha = hoje + timedelta(days=1)

    solicitacoes = SolicitacaoServico.objects.filter(
        status=SolicitacaoServico.STATUS_CONFIRMADO,
    ).select_related('usuario', 'servico', 'servico__profissional')
    if usuario is not None:
        solicitacoes = solicitacoes.filter(Q(usuario=usuario) | Q(servico__profissional=usuario))

    criados = 0
    for solicitacao in solicitacoes:
        for visita in regras.visitas_da_solicitacao(solicitacao):
            if visita.data == hoje:
                momento = 'dia'
            elif visita.data == amanha:
                momento = 'vespera'
            else:
                continue
            url = f'/servicos/solicitacao/{solicitacao.pk}/conversa/'
            profissional = solicitacao.servico.profissional
            cliente = solicitacao.usuario
            quando = 'HOJE' if momento == 'dia' else 'amanhã'
            for destino, outro in ((profissional, cliente), (cliente, profissional)):
                if usuario is not None and destino != usuario:
                    continue
                chave = f'lembrete-{momento}-{visita.chave}-{visita.data.isoformat()}-{destino.pk}'
                dica = ' Quando sair, toque em "Estou a caminho".' if (momento == 'dia' and destino == profissional) else ''
                if notificar(
                    destino,
                    f'Visita {quando}: {solicitacao.servico.nome}',
                    f'Com {nome_de(outro)} - {visita.turno_curto}.{dica}',
                    url=url, tipo='lembrete', chave=chave,
                ):
                    criados += 1
    return criados


# ---------------------------------------------------------------- ações pendentes (sino)

def acoes_pendentes(usuario):
    """Coisas que esperam uma decisão do usuário - aparecem no sino com
    botões, sem precisar abrir outras telas."""
    perfil = getattr(usuario, 'profile', None)
    acoes = {'pedidos': [], 'reagendamentos': [], 'orcamentos': []}

    if perfil and perfil.is_profissional:
        acoes['pedidos'] = list(
            SolicitacaoServico.objects.filter(
                servico__profissional=usuario, status=SolicitacaoServico.STATUS_PENDENTE,
            ).select_related('servico', 'usuario').order_by('-urgente', 'data_visita', '-criado_em')[:5]
        )

    acoes['reagendamentos'] = list(
        PropostaReagendamento.objects.filter(
            Q(solicitacao__usuario=usuario) | Q(solicitacao__servico__profissional=usuario),
            status=PropostaReagendamento.STATUS_PENDENTE,
            solicitacao__status=SolicitacaoServico.STATUS_CONFIRMADO,
        ).exclude(proposto_por=usuario).select_related('solicitacao', 'solicitacao__servico', 'proposto_por')[:5]
    )

    if perfil and perfil.is_usuario:
        acoes['orcamentos'] = list(
            SolicitacaoServico.objects.filter(
                usuario=usuario, status=SolicitacaoServico.STATUS_CONFIRMADO,
                orcamento__status='pendente',
            ).select_related('servico', 'orcamento')[:5]
        )
    return acoes
