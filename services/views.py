from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404

from accounts.decorators import professional_required, user_required
from .forms import ServicoForm, SolicitarServicoForm, BuscaServicoForm, MensagemSolicitacaoForm, AvaliacaoForm
from .models import (
    Servico,
    CategoriaServico,
    SolicitacaoServico,
    MensagemSolicitacao,
    Avaliacao,
    estrelas_da_media,
)


# ---------------------------------------------------------------------------
# Área do Usuário: U3 Opções de serviços -> U4..U8
# ---------------------------------------------------------------------------

def servico_list(request):
    """
    U4 - Visualizar serviços
    U5 - Buscar profissionais
    U6 - Filtrar por categoria
    Lê do "banco de dados de serviços" (D1) apenas os serviços disponíveis
    (alimentados por P9 - Serviço disponível para usuários).
    """
    form = BuscaServicoForm(request.GET or None)
    servicos = Servico.objects.filter(disponivel=True).select_related('categoria', 'profissional', 'profissional__profile').annotate(
        avaliacao_media=Avg('profissional__avaliacoes_recebidas__estrelas'),
        total_avaliacoes=Count('profissional__avaliacoes_recebidas', distinct=True),
    )

    if form.is_valid():
        q = form.cleaned_data.get('q')
        categoria = form.cleaned_data.get('categoria')
        if q:
            servicos = servicos.filter(
                Q(nome__icontains=q)
                | Q(descricao__icontains=q)
                | Q(profissional__username__icontains=q)
                | Q(profissional__first_name__icontains=q)
                | Q(profissional__last_name__icontains=q)
            )
        if categoria:
            servicos = servicos.filter(categoria=categoria)

    for servico in servicos:
        servico.avaliacao_estrelas = estrelas_da_media(servico.avaliacao_media)

    categorias = CategoriaServico.objects.all()
    return render(request, 'services/servico_list.html', {
        'servicos': servicos,
        'form': form,
        'categorias': categorias,
    })


def servico_detail(request, pk):
    """U7 - Consultar preço e duração (+ botão para U8 Solicitar serviço)."""
    servico = get_object_or_404(
        Servico.objects.select_related('categoria', 'profissional').annotate(
            avaliacao_media=Avg('profissional__avaliacoes_recebidas__estrelas'),
            total_avaliacoes=Count('profissional__avaliacoes_recebidas', distinct=True),
        ),
        pk=pk,
        disponivel=True,
    )
    servico.avaliacao_estrelas = estrelas_da_media(servico.avaliacao_media)
    return render(request, 'services/servico_detail.html', {'servico': servico})


@user_required
def servico_solicitar(request, pk):
    """U8 - Solicitar serviço (grava em D1 / cria uma SolicitacaoServico)."""
    servico = get_object_or_404(Servico, pk=pk, disponivel=True)
    if request.method == 'POST':
        form = SolicitarServicoForm(request.POST)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.servico = servico
            solicitacao.usuario = request.user
            solicitacao.save()
            messages.success(request, 'Solicitação enviada ao profissional com sucesso!')
            return redirect('services:minhas_solicitacoes')
    else:
        form = SolicitarServicoForm()
    return render(request, 'services/servico_solicitar.html', {'form': form, 'servico': servico})


@user_required
def minhas_solicitacoes(request):
    """Lista as solicitações feitas pelo usuário logado."""
    solicitacoes = SolicitacaoServico.objects.filter(usuario=request.user).select_related('servico')
    return render(request, 'services/minhas_solicitacoes.html', {'solicitacoes': solicitacoes})


@login_required
def mensagens(request):
    solicitacoes = SolicitacaoServico.objects.filter(
        Q(usuario=request.user) | Q(servico__profissional=request.user),
        status__in=[SolicitacaoServico.STATUS_CONFIRMADO, SolicitacaoServico.STATUS_CONCLUIDO],
    ).select_related('servico', 'usuario', 'servico__profissional').order_by('-criado_em')

    ultima_solicitacao = solicitacoes.first()
    if ultima_solicitacao:
        return redirect('services:conversa_solicitacao', pk=ultima_solicitacao.pk)
    return render(request, 'services/mensagens.html')


# ---------------------------------------------------------------------------
# Área do Profissional: O -> P3..P9
# ---------------------------------------------------------------------------

@professional_required
def meus_servicos(request):
    """Lista os serviços cadastrados pelo profissional logado."""
    servicos = Servico.objects.filter(profissional=request.user).select_related('categoria')
    return render(request, 'services/meus_servicos.html', {'servicos': servicos})


@professional_required
def servico_criar(request):
    """P3 Adicionar serviço -> P4 nome, P5 descrição, P6 preço, P7 duração, P8 salvar."""
    if request.method == 'POST':
        form = ServicoForm(request.POST)
        if form.is_valid():
            servico = form.save(commit=False)
            servico.profissional = request.user
            servico.save()  # P8 - Salvar serviço -> grava em D1 e fica disponível (P9)
            messages.success(request, 'Serviço cadastrado com sucesso!')
            return redirect('services:meus_servicos')
    else:
        form = ServicoForm()
    return render(request, 'services/servico_form.html', {'form': form, 'modo': 'criar'})


@professional_required
def servico_editar(request, pk):
    servico = get_object_or_404(Servico, pk=pk, profissional=request.user)
    if request.method == 'POST':
        form = ServicoForm(request.POST, instance=servico)
        if form.is_valid():
            form.save()
            messages.success(request, 'Serviço atualizado com sucesso!')
            return redirect('services:meus_servicos')
    else:
        form = ServicoForm(instance=servico)
    return render(request, 'services/servico_form.html', {'form': form, 'modo': 'editar', 'servico': servico})


@professional_required
def servico_excluir(request, pk):
    servico = get_object_or_404(Servico, pk=pk, profissional=request.user)
    if request.method == 'POST':
        servico.delete()
        messages.success(request, 'Serviço removido.')
        return redirect('services:meus_servicos')
    return render(request, 'services/servico_confirm_delete.html', {'servico': servico})


@professional_required
def solicitacoes_recebidas(request):
    """Solicitações recebidas para os serviços do profissional logado."""
    solicitacoes = SolicitacaoServico.objects.filter(
        servico__profissional=request.user
    ).select_related('servico', 'usuario', 'usuario__profile')
    return render(request, 'services/solicitacoes_recebidas.html', {'solicitacoes': solicitacoes})


@professional_required
@require_POST
def atualizar_status_solicitacao(request, pk, acao):
    solicitacao = get_object_or_404(
        SolicitacaoServico.objects.select_related('servico'),
        pk=pk,
        servico__profissional=request.user,
        status=SolicitacaoServico.STATUS_PENDENTE,
    )

    if acao == 'aceitar':
        solicitacao.status = SolicitacaoServico.STATUS_CONFIRMADO
        mensagem = 'Solicitação aceita com sucesso.'
    elif acao == 'recusar':
        solicitacao.status = SolicitacaoServico.STATUS_CANCELADO
        mensagem = 'Solicitação recusada.'
    else:
        messages.error(request, 'Ação de solicitação inválida.')
        return redirect('services:solicitacoes_recebidas')

    solicitacao.save(update_fields=['status'])
    messages.success(request, mensagem)
    return redirect('services:solicitacoes_recebidas')


@login_required
def conversa_solicitacao(request, pk):
    solicitacao = get_object_or_404(
        SolicitacaoServico.objects.select_related('servico', 'usuario', 'servico__profissional'),
        pk=pk,
        status__in=[SolicitacaoServico.STATUS_CONFIRMADO, SolicitacaoServico.STATUS_CONCLUIDO],
    )
    if request.user not in (solicitacao.usuario, solicitacao.servico.profissional):
        messages.error(request, 'Você não tem acesso a esta conversa.')
        return redirect('home')

    solicitacao.mensagens.filter(lida=False).exclude(autor=request.user).update(lida=True)
    mensagens = solicitacao.mensagens.select_related('autor').all()
    conversas = SolicitacaoServico.objects.filter(
        Q(usuario=request.user) | Q(servico__profissional=request.user),
        status__in=[SolicitacaoServico.STATUS_CONFIRMADO, SolicitacaoServico.STATUS_CONCLUIDO],
    ).select_related('servico', 'usuario', 'servico__profissional').order_by('-criado_em')
    avaliacao = getattr(solicitacao, 'avaliacao', None)
    avaliacao_form = AvaliacaoForm(instance=avaliacao)
    if request.method == 'POST' and solicitacao.status == SolicitacaoServico.STATUS_CONFIRMADO:
        form = MensagemSolicitacaoForm(request.POST)
        if form.is_valid():
            mensagem = form.save(commit=False)
            mensagem.solicitacao = solicitacao
            mensagem.autor = request.user
            mensagem.save()
            return redirect('services:conversa_solicitacao', pk=solicitacao.pk)
    else:
        form = MensagemSolicitacaoForm()

    return render(request, 'services/conversa_solicitacao.html', {
        'solicitacao': solicitacao,
        'mensagens': mensagens,
        'conversas': conversas,
        'form': form,
        'avaliacao': avaliacao,
        'avaliacao_form': avaliacao_form,
    })


@login_required
@require_POST
def concluir_solicitacao(request, pk):
    solicitacao = get_object_or_404(
        SolicitacaoServico,
        pk=pk,
        usuario=request.user,
        status=SolicitacaoServico.STATUS_CONFIRMADO,
    )
    solicitacao.status = SolicitacaoServico.STATUS_CONCLUIDO
    solicitacao.save(update_fields=['status'])
    messages.success(request, 'Serviço concluído com sucesso.')
    return redirect('services:conversa_solicitacao', pk=solicitacao.pk)


@login_required
@require_POST
def avaliar_solicitacao(request, pk):
    solicitacao = get_object_or_404(
        SolicitacaoServico.objects.select_related('servico'),
        pk=pk,
        usuario=request.user,
        status=SolicitacaoServico.STATUS_CONCLUIDO,
    )
    avaliacao = getattr(solicitacao, 'avaliacao', None)
    form = AvaliacaoForm(request.POST, instance=avaliacao)
    if form.is_valid():
        avaliacao = form.save(commit=False)
        avaliacao.solicitacao = solicitacao
        avaliacao.usuario = request.user
        avaliacao.profissional = solicitacao.servico.profissional
        avaliacao.save()
        messages.success(request, 'Avaliação registrada com sucesso.')
    return redirect('services:conversa_solicitacao', pk=pk)
