from django.db.models import Q
from django.utils import timezone

from . import pagamentos
from .models import CategoriaServico, Favorito, MensagemSolicitacao, Orcamento, SolicitacaoServico
from .notificacoes import acoes_pendentes, gerar_lembretes

INTERVALO_LEMBRETES_SEGUNDOS = 600


def mensagens_nao_lidas_qs(user):
    return MensagemSolicitacao.objects.filter(
        Q(solicitacao__usuario=user) | Q(solicitacao__servico__profissional=user),
        lida=False,
    ).exclude(autor=user).exclude(
        solicitacao__status=SolicitacaoServico.STATUS_CONCLUIDO,
        solicitacao__avaliacao__isnull=False,
    )


def contagens_do_usuario(user):
    """Números dos balões vermelhos (menu, barra de baixo e título da aba).
    Usado pelas telas normais e pelo endpoint de atualização em tempo real."""
    return {
        'mensagens': mensagens_nao_lidas_qs(user).count(),
        'solicitacoes': SolicitacaoServico.objects.filter(
            servico__profissional=user, status=SolicitacaoServico.STATUS_PENDENTE,
        ).count(),
        # Cliente: orçamentos enviados que ele ainda não abriu.
        # Profissional: solicitações "Aguardando valor" (visita concluída,
        # orçamento ainda não enviado).
        'orcamentos': Orcamento.objects.filter(
            solicitacao__usuario=user,
            solicitacao__status=SolicitacaoServico.STATUS_CONFIRMADO,
            visualizado_pelo_cliente=False,
        ).count() + SolicitacaoServico.objects.filter(
            servico__profissional=user,
            status=SolicitacaoServico.STATUS_CONFIRMADO,
            visita_concluida_em__isnull=False,
            orcamento__isnull=True,
        ).count(),
    }


def dados_do_sino(user):
    """Conteúdo do sino de notificações: ações pendentes + avisos não lidos."""
    acoes = acoes_pendentes(user)
    nao_lidas = list(user.notificacoes.filter(lida=False)[:8])
    total_nao_lidas = user.notificacoes.filter(lida=False).count()
    total = total_nao_lidas + len(acoes['pedidos']) + len(acoes['reagendamentos']) + len(acoes['orcamentos'])
    assinatura = '-'.join(str(x) for x in (
        total,
        nao_lidas[0].pk if nao_lidas else 0,
        ','.join(str(p.pk) for p in acoes['pedidos']),
        ','.join(str(r.pk) for r in acoes['reagendamentos']),
        ','.join(str(o.pk) for o in acoes['orcamentos']),
    ))
    return {
        'sino_acoes': acoes,
        'sino_notificacoes': nao_lidas,
        'sino_total': total,
        'sino_assinatura': assinatura,
    }


def notificacoes_mensagens(request):
    categorias_rodape = list(CategoriaServico.objects.all())
    if not request.user.is_authenticated:
        return {
            'categorias_rodape': categorias_rodape,
            'sino_total': 0,
            'toast_pedidos': [],
            'mensagens_nao_lidas': [],
            'total_mensagens_nao_lidas': 0,
            'total_solicitacoes_pendentes': 0,
            'tem_orcamentos_visiveis': False,
            'total_orcamentos_novos': 0,
            'tem_favoritos': False,
        }

    user = request.user

    # Lembretes de visita ("amanhã" / "hoje"): gerados enquanto o usuário
    # usa o site, no máximo a cada 10 minutos por sessão. O comando
    # `enviar_lembretes` faz o mesmo para todos, para rodar em agendador.
    agora = timezone.now().timestamp()
    if agora - request.session.get('lembretes_ts', 0) > INTERVALO_LEMBRETES_SEGUNDOS:
        gerar_lembretes(user)
        request.session['lembretes_ts'] = agora

    sino = dados_do_sino(user)
    contagens = contagens_do_usuario(user)

    # Pedidos novos (para o profissional) ainda não "anunciados" nesta
    # sessão aparecem como notificação com botões Aceitar / Recusar.
    ja_avisados = set(request.session.get('pedidos_avisados', []))
    toast_pedidos = [p for p in sino['sino_acoes']['pedidos'] if p.pk not in ja_avisados][:2]
    if toast_pedidos:
        request.session['pedidos_avisados'] = list(ja_avisados | {p.pk for p in toast_pedidos})[-100:]

    contexto = {
        'pix_habilitado': pagamentos.habilitado(),
        'toast_pedidos': toast_pedidos,
        'categorias_rodape': categorias_rodape,
        'mensagens_nao_lidas': mensagens_nao_lidas_qs(user).select_related(
            'solicitacao', 'solicitacao__servico', 'autor',
        )[:5],
        'total_mensagens_nao_lidas': contagens['mensagens'],
        'total_solicitacoes_pendentes': contagens['solicitacoes'],
        # A aba "Orçamentos" do menu de cima só aparece enquanto existir pelo
        # menos uma solicitação ativa em que o cliente já apertou "Visita
        # concluída" (a barra de baixo do celular mostra sempre).
        'tem_orcamentos_visiveis': SolicitacaoServico.objects.filter(
            Q(usuario=user) | Q(servico__profissional=user),
            status=SolicitacaoServico.STATUS_CONFIRMADO,
            visita_concluida_em__isnull=False,
        ).exists(),
        'total_orcamentos_novos': contagens['orcamentos'],
        # O link "Favoritos" só aparece no menu depois que o cliente
        # favoritar pelo menos um profissional.
        'tem_favoritos': Favorito.objects.filter(usuario=user).exists(),
    }
    contexto.update(sino)
    contexto['pagina_atual'] = request.get_full_path()
    return contexto
