"""Endpoints de atualização em tempo real (o navegador consulta a cada poucos
segundos; nada de recarregar a página).

Funciona em qualquer hospedagem. Se um dia o volume crescer, a troca natural
é WebSocket (Django Channels) - o formato das respostas já está pronto para
isso: são só "mensagens novas + quem já leu + contagens".
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET

from .context_processors import contagens_do_usuario, dados_do_sino
from .models import MensagemSolicitacao, SolicitacaoServico
from .views import montar_lista_conversas


def _pulso(user):
    contagens = contagens_do_usuario(user)
    sino = dados_do_sino(user)
    return {
        'mensagens': contagens['mensagens'],
        'orcamentos': contagens['orcamentos'],
        'solicitacoes': contagens['solicitacoes'],
        'sino': sino['sino_total'],
        'sino_assinatura': sino['sino_assinatura'],
    }


@login_required
@require_GET
def pulso(request):
    """Números dos balões (menu, barra de baixo, título da aba)."""
    return JsonResponse(_pulso(request.user))


@login_required
@require_GET
def sino_menu(request):
    """Conteúdo atualizado do sino de notificações."""
    contexto = dados_do_sino(request.user)
    pagina = request.GET.get('pagina', '')
    contexto['pagina_atual'] = pagina if pagina.startswith('/') and not pagina.startswith('//') else '/'
    html = render_to_string('_sino_menu.html', contexto, request=request)
    return JsonResponse({'html': html, 'total': contexto['sino_total'], 'assinatura': contexto['sino_assinatura']})


@login_required
@require_GET
def mensagens_novas(request, pk):
    solicitacao = get_object_or_404(
        SolicitacaoServico.objects.select_related('servico'),
        pk=pk, status__in=[SolicitacaoServico.STATUS_CONFIRMADO, SolicitacaoServico.STATUS_CONCLUIDO],
    )
    if request.user not in (solicitacao.usuario, solicitacao.servico.profissional):
        raise Http404

    try:
        depois = int(request.GET.get('depois', 0))
    except ValueError:
        depois = 0
    pendentes = []
    for bruto in request.GET.get('pendentes', '').split(','):
        if bruto.strip().isdigit():
            pendentes.append(int(bruto))
    pendentes = pendentes[:200]
    data_ultima = request.GET.get('data_ultima', '')
    visivel = request.GET.get('visivel') == '1'

    novas = list(
        solicitacao.mensagens.filter(pk__gt=depois).select_related('autor').order_by('pk')
    )
    # Quem está com a conversa aberta e visível "leu" o que chegou agora.
    if visivel:
        ids_para_ler = [m.pk for m in novas if m.autor_id != request.user.id and not m.lida]
        if ids_para_ler:
            MensagemSolicitacao.objects.filter(pk__in=ids_para_ler).update(lida=True)
        # Também marca como lidas mensagens antigas que ainda estivessem abertas.
        solicitacao.mensagens.filter(lida=False).exclude(autor=request.user).update(lida=True)

    itens = []
    for mensagem in novas:
        data = timezone.localtime(mensagem.criada_em).strftime('%d/%m/%Y')
        divisor = data if data != data_ultima else ''
        data_ultima = data
        itens.append({
            'id': mensagem.pk,
            'minha': mensagem.autor_id == request.user.id,
            'html': render_to_string(
                'services/_mensagem.html',
                {'mensagem': mensagem, 'divisor_data': divisor},
                request=request,
            ),
        })

    lidas = []
    if pendentes:
        lidas = list(
            solicitacao.mensagens.filter(pk__in=pendentes, autor=request.user, lida=True).values_list('pk', flat=True)
        )

    return JsonResponse({
        'mensagens': itens,
        'lidas': lidas,
        'status': solicitacao.status,
        'pulso': _pulso(request.user),
    })


@login_required
@require_GET
def conversas_resumo(request):
    """Lista lateral de conversas (prévia, hora, não lidas), já renderizada."""
    ativa = request.GET.get('ativa')
    ativa_pk = int(ativa) if ativa and ativa.isdigit() else None
    conversas = montar_lista_conversas(request.user)
    return JsonResponse({
        'conversas': [
            {
                'pk': conversa.pk,
                'html': render_to_string(
                    'services/_conversa_item.html',
                    {'conversa': conversa, 'ativa_pk': ativa_pk},
                    request=request,
                ),
            }
            for conversa in conversas
        ],
        'pulso': _pulso(request.user),
    })
