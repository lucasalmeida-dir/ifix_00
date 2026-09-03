from django.db.models import Q

from .models import MensagemSolicitacao, SolicitacaoServico


def notificacoes_mensagens(request):
    if not request.user.is_authenticated:
        return {
            'mensagens_nao_lidas': [],
            'total_mensagens_nao_lidas': 0,
            'total_solicitacoes_pendentes': 0,
        }

    mensagens = MensagemSolicitacao.objects.filter(
        Q(solicitacao__usuario=request.user)
        | Q(solicitacao__servico__profissional=request.user),
        lida=False,
    ).exclude(autor=request.user).select_related('solicitacao', 'solicitacao__servico', 'autor')

    return {
        'mensagens_nao_lidas': mensagens[:5],
        'total_mensagens_nao_lidas': mensagens.count(),
        'total_solicitacoes_pendentes': SolicitacaoServico.objects.filter(
            servico__profissional=request.user,
            status=SolicitacaoServico.STATUS_PENDENTE,
        ).count(),
    }