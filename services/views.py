from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404

from accounts.decorators import professional_required, user_required
from .forms import ServicoForm, SolicitarServicoForm, BuscaServicoForm
from .models import Servico, CategoriaServico, SolicitacaoServico


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
    servicos = Servico.objects.filter(disponivel=True).select_related('categoria', 'profissional')

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

    categorias = CategoriaServico.objects.all()
    return render(request, 'services/servico_list.html', {
        'servicos': servicos,
        'form': form,
        'categorias': categorias,
    })


def servico_detail(request, pk):
    """U7 - Consultar preço e duração (+ botão para U8 Solicitar serviço)."""
    servico = get_object_or_404(Servico, pk=pk, disponivel=True)
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
    ).select_related('servico', 'usuario')
    return render(request, 'services/solicitacoes_recebidas.html', {'solicitacoes': solicitacoes})
