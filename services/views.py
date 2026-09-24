import calendar
import json
import uuid
from datetime import date
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count, F, Q
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404

from accounts.decorators import professional_required, user_required
from accounts.models import Profile
from accounts.seguranca import existe_bloqueio, ids_com_bloqueio
from accounts.services import calcular_distancia_km
import seo
from . import pagamentos, regras
from .notificacoes import gerar_lembretes, nome_de, notificar
from .catalogo import CATALOGO_SERVICOS
from .perfil import tempo_resposta
from .forms import (
    MAX_ANEXOS,
    ServicoForm,
    ServicoEmLoteForm,
    SolicitarServicoForm,
    BuscaServicoForm,
    MensagemSolicitacaoForm,
    AvaliacaoForm,
    AvaliacaoRespostaForm,
    OrcamentoForm,
    DiaVisitaFormSet,
)
from .models import (
    Servico,
    CategoriaServico,
    Favorito,
    AnexoSolicitacao,
    DiaVisitaOrcamento as _DiaVisitaOrcamento,
    SolicitacaoServico,
    MensagemSolicitacao,
    Avaliacao,
    Orcamento,
    DiaVisitaOrcamento,
    estrelas_da_media,
)


MAX_PROFISSIONAIS_PEDIDO = 5

MESES_PT = (
    '', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
)


def _mes_adjacente(ano, mes, deslocamento):
    """Soma/subtrai um mês (deslocamento = 1 ou -1) a partir de ano/mês."""
    indice = (ano * 12 + (mes - 1)) + deslocamento
    return indice // 12, indice % 12 + 1


def _construir_calendario(ano, mes):
    """Monta as semanas do mês/ano informados para o calendário de U8.

    Cada dia carrega a data, se pertence ao mês exibido e se pode ser
    escolhido pelo cliente (hoje ou qualquer data futura).
    """
    hoje = timezone.localdate()
    cal = calendar.Calendar(firstweekday=6)  # semana começa no domingo
    semanas = []
    for semana in cal.monthdatescalendar(ano, mes):
        semanas.append([
            {
                'data': dia,
                'no_mes': dia.month == mes,
                'selecionavel': dia >= hoje,
                'hoje': dia == hoje,
            }
            for dia in semana
        ])
    return semanas


# ---------------------------------------------------------------------------
# Área do Usuário: U3 Opções de serviços -> U4..U8
# ---------------------------------------------------------------------------

def servico_list(request, slug=None, cidade_slug=None):
    """
    U4 - Visualizar serviços
    U5 - Buscar profissionais
    U6 - Filtrar por categoria
    Lê todos os serviços cadastrados no "banco de dados de serviços" (D1).

    Quando vem com `cidade_slug` (rota .../categoria/<slug>/em/<cidade>/),
    é uma página do tipo "Eletricista em Campinas" - pensada para trazer
    tráfego de busca (cada combinação categoria+cidade com profissional
    cadastrado vira uma URL própria, indexável, listada no sitemap).
    """
    categoria_pagina = get_object_or_404(CategoriaServico, slug=slug) if slug else None
    cidade_pagina = None
    if cidade_slug:
        perfil_da_cidade = Profile.objects.filter(cidade_slug=cidade_slug).exclude(cidade='').first()
        if not perfil_da_cidade:
            raise Http404
        cidade_pagina = {'slug': cidade_slug, 'nome': perfil_da_cidade.cidade, 'uf': perfil_da_cidade.uf}

    form = BuscaServicoForm(request.GET or None)
    servicos = Servico.objects.select_related('categoria', 'profissional', 'profissional__profile').annotate(
        avaliacao_media=Avg('profissional__avaliacoes_recebidas__estrelas'),
        total_avaliacoes=Count('profissional__avaliacoes_recebidas', distinct=True),
    )

    # Contas excluídas/bloqueadas pela equipe e pessoas com bloqueio (nos dois
    # sentidos) não aparecem na busca.
    servicos = servicos.filter(profissional__is_active=True).exclude(
        profissional_id__in=ids_com_bloqueio(request.user),
    )

    # Um profissional não enxerga os cards dos outros profissionais aqui -
    # só o próprio, já que essa tela é a vitrine para o cliente buscar
    # quem contratar.
    perfil_logado = getattr(request.user, 'profile', None) if request.user.is_authenticated else None
    if perfil_logado and perfil_logado.is_profissional:
        servicos = servicos.filter(profissional=request.user)

    if categoria_pagina:
        servicos = servicos.filter(categoria=categoria_pagina)
    if cidade_pagina:
        servicos = servicos.filter(profissional__profile__cidade_slug=cidade_pagina['slug'])

    ordenar = ''
    if form.is_valid():
        q = form.cleaned_data.get('q')
        categoria = form.cleaned_data.get('categoria')
        ordenar = form.cleaned_data.get('ordenar')
        if q:
            servicos = servicos.filter(
                Q(nome__icontains=q)
                | Q(subservico__icontains=q)
                | Q(descricao__icontains=q)
                | Q(categoria__nome__icontains=q)
                | Q(profissional__username__icontains=q)
                | Q(profissional__first_name__icontains=q)
                | Q(profissional__last_name__icontains=q)
            )
        if categoria:
            servicos = servicos.filter(categoria=categoria)

    if ordenar == 'preco':
        servicos = servicos.order_by('preco_min')
    elif ordenar == 'avaliacao':
        servicos = servicos.order_by(F('avaliacao_media').desc(nulls_last=True), '-total_avaliacoes')

    # Perfil do cliente logado (se houver) para calcular a distância até
    # cada profissional a partir das coordenadas obtidas via CEP.
    perfil_usuario = getattr(request.user, 'profile', None) if request.user.is_authenticated else None
    calcular_distancia = bool(perfil_usuario and perfil_usuario.tem_localizacao)

    servicos = list(servicos)
    for servico in servicos:
        servico.avaliacao_estrelas = estrelas_da_media(servico.avaliacao_media)
        servico.distancia_km = None
        if calcular_distancia:
            perfil_profissional = getattr(servico.profissional, 'profile', None)
            if perfil_profissional and perfil_profissional.tem_localizacao:
                servico.distancia_km = calcular_distancia_km(
                    perfil_usuario.latitude, perfil_usuario.longitude,
                    perfil_profissional.latitude, perfil_profissional.longitude,
                )

    # "Mais próximos" só vale quando o cliente tem localização cadastrada -
    # sem isso fica sem efeito (o card avisa, via `distancia_disponivel`,
    # para ele cadastrar o CEP).
    if calcular_distancia and ordenar == 'distancia':
        servicos.sort(key=lambda s: (s.distancia_km is None, s.distancia_km))

    favoritos_ids = set()
    if request.user.is_authenticated:
        favoritos_ids = set(
            Favorito.objects.filter(usuario=request.user, servico__in=[s.pk for s in servicos])
            .values_list('servico_id', flat=True)
        )

    categorias = CategoriaServico.objects.all()

    # --- SEO: título/descrição próprios por categoria/cidade e dados estruturados ---
    caminhos = [('Início', '/'), ('Serviços', reverse('services:servico_list'))]
    if categoria_pagina:
        profissao = CATALOGO_SERVICOS.get(categoria_pagina.slug, {}).get('servico', categoria_pagina.nome)
        caminhos.append((categoria_pagina.nome, categoria_pagina.get_absolute_url()))
        if cidade_pagina:
            local = f"{cidade_pagina['nome']}/{cidade_pagina['uf']}" if cidade_pagina['uf'] else cidade_pagina['nome']
            seo_titulo = f"{profissao} em {cidade_pagina['nome']}: preços e avaliações | IFIX"
            seo_descricao = (
                f"Contrate {profissao.lower()} em {local}. Compare o preço da visita, veja avaliações "
                'reais de clientes e agende pelo celular no IFIX.'
            )
            seo_h1 = f"{profissao} em {cidade_pagina['nome']}"
            caminhos.append((cidade_pagina['nome'], request.path))
        else:
            seo_titulo = f'{profissao} perto de você: preços e avaliações | IFIX'
            seo_descricao = (
                f'Contrate {profissao.lower()} avaliado perto de você. Compare o preço da visita, '
                'veja avaliações reais de clientes e agende pelo celular no IFIX.'
            )
            seo_h1 = f'{profissao} perto de você'
    else:
        seo_titulo = 'Encontrar profissionais de serviços residenciais | IFIX'
        seo_descricao = (
            'Encontre eletricista, encanador, marceneiro e pintor avaliados perto de você. '
            'Compare preços da visita e agende pelo celular.'
        )
        seo_h1 = 'Encontrar profissional'

    tem_filtro = bool(request.GET.get('q') or request.GET.get('categoria') or request.GET.get('ordenar'))
    return render(request, 'services/servico_list.html', {
        'servicos': servicos,
        'form': form,
        'categorias': categorias,
        'distancia_disponivel': calcular_distancia,
        'categoria_pagina': categoria_pagina,
        'cidade_pagina': cidade_pagina,
        'favoritos_ids': favoritos_ids,
        'seo_titulo': seo_titulo,
        'seo_descricao': seo_descricao,
        'seo_h1': seo_h1,
        'seo_robots': 'noindex,follow' if tem_filtro else 'index,follow,max-image-preview:large',
        'seo_canonical': seo.url_absoluta(request, request.path),
        'json_ld': seo.json_ld(seo.breadcrumb_ld(request, caminhos)),
    })


@user_required
def mapa_profissionais(request):
    """Mapa com a localização aproximada dos profissionais (baseada no
    CEP que cada um cadastrou), com um círculo com a foto de cada um -
    tela exclusiva do cliente, para ele ter uma noção visual de quem
    está perto sem que o profissional precise expor o endereço exato."""
    perfil_cliente = getattr(request.user, 'profile', None)

    profissionais_qs = Profile.objects.filter(
        tipo=Profile.TIPO_PROFISSIONAL,
        latitude__isnull=False,
        longitude__isnull=False,
        user__servicos__isnull=False,
    ).select_related('user').prefetch_related('especialidades').distinct()

    profissionais = []
    for perfil in profissionais_qs:
        profissionais.append({
            'nome': perfil.user.get_full_name() or perfil.user.username,
            'foto': perfil.foto.url if perfil.foto else '',
            'lat': perfil.latitude,
            'lng': perfil.longitude,
            'especialidades': ', '.join(perfil.especialidades.values_list('nome', flat=True)),
            'buscaUrl': f"{reverse('services:servico_list')}?q={quote(perfil.user.username)}",
        })

    centro = None
    if perfil_cliente and perfil_cliente.tem_localizacao:
        centro = {'lat': perfil_cliente.latitude, 'lng': perfil_cliente.longitude}

    return render(request, 'services/mapa_profissionais.html', {
        'profissionais_json': json.dumps(profissionais),
        'centro_json': json.dumps(centro),
        'total_profissionais': len(profissionais),
    })


def servico_detail(request, slug):
    """U7 - Consultar preço e duração (+ botão para U8 Solicitar serviço)."""
    servico = get_object_or_404(
        Servico.objects.select_related('categoria', 'profissional').annotate(
            avaliacao_media=Avg('profissional__avaliacoes_recebidas__estrelas'),
            total_avaliacoes=Count('profissional__avaliacoes_recebidas', distinct=True),
        ),
        slug=slug,
    )
    if not servico.profissional.is_active or servico.profissional_id in ids_com_bloqueio(request.user):
        raise Http404
    servico.avaliacao_estrelas = estrelas_da_media(servico.avaliacao_media)

    servico.distancia_km = None
    perfil_usuario = getattr(request.user, 'profile', None) if request.user.is_authenticated else None
    if perfil_usuario and perfil_usuario.tem_localizacao:
        perfil_profissional = getattr(servico.profissional, 'profile', None)
        if perfil_profissional and perfil_profissional.tem_localizacao:
            servico.distancia_km = calcular_distancia_km(
                perfil_usuario.latitude, perfil_usuario.longitude,
                perfil_profissional.latitude, perfil_profissional.longitude,
            )

    avaliacoes = Avaliacao.objects.filter(
        profissional=servico.profissional,
    ).exclude(comentario='').select_related('usuario').order_by('-criado_em')[:10]

    eh_favorito = (
        request.user.is_authenticated
        and Favorito.objects.filter(usuario=request.user, servico=servico).exists()
    )

    nome_prof = servico.profissional.get_full_name() or servico.profissional.username
    sub = f' - {servico.subservico}' if servico.subservico else ''
    caminhos = [('Início', '/'), ('Serviços', reverse('services:servico_list')),
                (servico.categoria.nome, servico.categoria.get_absolute_url()),
                (servico.nome, servico.get_absolute_url())]
    return render(request, 'services/servico_detail.html', {
        'servico': servico,
        'nome_profissional': nome_prof,
        'avaliacoes': avaliacoes,
        'eh_favorito': eh_favorito,
        'seo_titulo': f'{servico.nome}{sub} com {nome_prof} | IFIX',
        'seo_descricao': (
            f'{servico.nome}{sub} com {nome_prof}: visita a partir de R$ {servico.preco_min}, '
            f'duração de {servico.duracao_minutos} min. Veja avaliações e solicite a visita no IFIX.'
        ),
        'json_ld': seo.json_ld(seo.servico_ld(request, servico), seo.breadcrumb_ld(request, caminhos)),
    })


def perfil_profissional(request, pk):
    """Página pública do profissional: foto, selo, avaliações, tempo de
    resposta, serviços e o link da página/site dele."""
    perfil = get_object_or_404(
        Profile.objects.select_related('user').prefetch_related('especialidades'),
        user_id=pk, tipo=Profile.TIPO_PROFISSIONAL, user__is_active=True,
    )
    profissional = perfil.user
    if profissional.pk in ids_com_bloqueio(request.user):
        raise Http404

    avaliacoes_qs = Avaliacao.objects.filter(profissional=profissional)
    resumo = avaliacoes_qs.aggregate(media=Avg('estrelas'), total=Count('pk'))
    avaliacoes = avaliacoes_qs.select_related('usuario').order_by('-criado_em')[:20]
    concluidos = SolicitacaoServico.objects.filter(
        servico__profissional=profissional, status=SolicitacaoServico.STATUS_CONCLUIDO,
    ).count()

    nome = profissional.get_full_name() or profissional.username
    cidade = perfil.cidade + (f'/{perfil.uf}' if perfil.uf else '') if perfil.cidade else ''
    return render(request, 'services/perfil_profissional.html', {
        'perfil': perfil,
        'profissional': profissional,
        'nome_profissional': nome,
        'cidade': cidade,
        'avaliacoes': avaliacoes,
        'media': resumo['media'],
        'estrelas': estrelas_da_media(resumo['media']),
        'total_avaliacoes': resumo['total'],
        'concluidos': concluidos,
        'tempo_resposta': tempo_resposta(profissional),
        'eh_o_proprio': request.user.is_authenticated and request.user.pk == profissional.pk,
        'seo_titulo': f'{nome}, profissional no IFIX' + (f' em {perfil.cidade}' if perfil.cidade else ''),
        'seo_descricao': (
            f'Veja o perfil de {nome}: '
            + (f'{perfil.especialidades_texto}, ' if perfil.especialidades_texto else '')
            + 'avaliações de clientes, tempo de resposta e serviços no IFIX.'
        ),
    })


@user_required
@require_POST
def favorito_toggle(request, pk):
    """Marca/desmarca um serviço como favorito - usado pelo botão de
    coração nos cards e na página do serviço."""
    servico = get_object_or_404(Servico, pk=pk)
    favorito = Favorito.objects.filter(usuario=request.user, servico=servico).first()
    if favorito:
        favorito.delete()
        favoritado = False
    else:
        Favorito.objects.create(usuario=request.user, servico=servico)
        favoritado = True

    if request.headers.get('x-requested-with') == 'fetch':
        return JsonResponse({'favoritado': favoritado})

    destino = request.POST.get('next', '')
    if not destino.startswith('/') or destino.startswith('//'):
        destino = servico.get_absolute_url()
    return redirect(destino)


@user_required
def favoritos_lista(request):
    """"Meus favoritos" - serviços que o cliente marcou para achar de
    novo rápido, com atalho direto para "contratar de novo"."""
    favoritos = Favorito.objects.filter(usuario=request.user).select_related(
        'servico', 'servico__categoria', 'servico__profissional', 'servico__profissional__profile',
    ).annotate(
        avaliacao_media=Avg('servico__profissional__avaliacoes_recebidas__estrelas'),
        total_avaliacoes=Count('servico__profissional__avaliacoes_recebidas', distinct=True),
    )
    for favorito in favoritos:
        favorito.servico.avaliacao_estrelas = estrelas_da_media(favorito.avaliacao_media)
    return render(request, 'services/favoritos_lista.html', {'favoritos': favoritos})


@professional_required
@require_POST
def avaliacao_responder(request, pk):
    """O profissional responde a uma avaliação recebida e pode anexar uma
    foto do serviço concluído."""
    avaliacao = get_object_or_404(Avaliacao, pk=pk, profissional=request.user)
    form = AvaliacaoRespostaForm(request.POST, request.FILES, instance=avaliacao)
    if form.is_valid():
        resposta = form.save(commit=False)
        resposta.resposta_em = timezone.now()
        resposta.save()
        messages.success(request, 'Resposta enviada.')
    else:
        for erro in form.errors.get('__all__', []):
            messages.error(request, erro)
    destino = request.POST.get('next', '')
    if not destino.startswith('/') or destino.startswith('//'):
        destino = avaliacao.solicitacao.servico.get_absolute_url()
    return redirect(destino)


def _meses_do_calendario(quantidade=3):
    """Os próximos meses já montados (o calendário troca de mês só no
    navegador, sem recarregar a página - assim nada do que o cliente já
    preencheu se perde ao folhear os meses)."""
    hoje = timezone.localdate()
    ano, mes = hoje.year, hoje.month
    meses = []
    for _ in range(quantidade):
        meses.append({
            'nome': MESES_PT[mes],
            'ano': ano,
            'semanas': _construir_calendario(ano, mes),
        })
        ano, mes = _mes_adjacente(ano, mes, 1)
    return meses


def _endereco_do_perfil(user):
    perfil = getattr(user, 'profile', None)
    if not perfil or not perfil.endereco:
        return ''
    partes = [perfil.endereco, perfil.numero, perfil.complemento]
    return ', '.join(p for p in partes if p)


def _processar_solicitacao(request, servicos, template, contexto_extra=None):
    """Tela de pedido de visita, usada tanto para um profissional
    (`servico_solicitar`) quanto para vários de uma vez (`solicitar_varios`).
    Cria uma SolicitacaoServico para cada serviço escolhido, todas com os
    mesmos dados (dia, turno, urgência, descrição, GPS e anexos). Quando são
    vários, os pedidos dividem um `grupo`, que alimenta a tela de comparação.
    """
    if request.method == 'POST':
        form = SolicitarServicoForm(request.POST, request.FILES)
        if form.is_valid():
            anexos = form.cleaned_data.get('anexos') or []
            grupo = uuid.uuid4() if len(servicos) > 1 else None
            criadas = []
            with transaction.atomic():
                base = form.save(commit=False)
                for servico in servicos:
                    solicitacao = SolicitacaoServico(
                        servico=servico, usuario=request.user, grupo=grupo,
                        data_visita=base.data_visita, turno=base.turno, urgente=base.urgente,
                        mensagem=base.mensagem, endereco_visita=base.endereco_visita,
                        latitude=base.latitude, longitude=base.longitude,
                    )
                    solicitacao.save()
                    criadas.append(solicitacao)

                # O arquivo é gravado uma única vez; os pedidos seguintes
                # apenas apontam para o mesmo arquivo.
                for arquivo in anexos:
                    primeiro = AnexoSolicitacao.objects.create(solicitacao=criadas[0], arquivo=arquivo)
                    for solicitacao in criadas[1:]:
                        AnexoSolicitacao.objects.create(solicitacao=solicitacao, arquivo=primeiro.arquivo.name)

            for solicitacao in criadas:
                prefixo = 'URGENTE - ' if solicitacao.urgente else ''
                notificar(
                    solicitacao.servico.profissional, f'{prefixo}Novo pedido de visita',
                    f'{nome_de(request.user)} pediu {solicitacao.servico.nome} para '
                    f'{solicitacao.data_visita:%d/%m} ({solicitacao.turno_curto}).',
                    url=reverse('services:solicitacoes_recebidas'), tipo='novo_pedido',
                    chave=f'novo-pedido-{solicitacao.pk}',
                )
            data_txt = criadas[0].data_visita.strftime('%d/%m/%Y')
            if grupo:
                messages.success(
                    request,
                    f'Pedido enviado para {len(criadas)} profissionais. Compare as respostas por aqui '
                    'assim que eles responderem.',
                )
                return redirect('services:comparar_pedido', grupo=grupo)
            messages.success(
                request,
                f'Visita solicitada para o dia {data_txt}. Você será avisado assim que o profissional aceitar.',
            )
            return redirect('services:minhas_solicitacoes')
    else:
        form = SolicitarServicoForm(initial={'endereco_visita': _endereco_do_perfil(request.user)})

    contexto = {
        'form': form,
        'servicos': servicos,
        'servico': servicos[0],
        'meses': _meses_do_calendario(),
        'hoje_iso': timezone.localdate().isoformat(),
        'max_anexos': MAX_ANEXOS,
    }
    contexto.update(contexto_extra or {})
    return render(request, template, contexto)


@user_required
def servico_solicitar(request, pk):
    """U8 - Solicitar visita a um profissional."""
    servico = get_object_or_404(
        Servico.objects.select_related('profissional', 'categoria'), pk=pk, profissional__is_active=True,
    )
    if servico.profissional_id in ids_com_bloqueio(request.user):
        messages.error(request, 'Não é possível pedir serviço a esta pessoa (há um bloqueio entre vocês).')
        return redirect('services:servico_list')
    return _processar_solicitacao(request, [servico], 'services/servico_solicitar.html')


@user_required
def solicitar_varios(request):
    """Pede a mesma visita para vários profissionais ao mesmo tempo (até 5),
    para depois comparar as respostas."""
    ids = request.POST.getlist('s') if request.method == 'POST' else request.GET.getlist('s')
    try:
        ids = list(dict.fromkeys(int(i) for i in ids))[:MAX_PROFISSIONAIS_PEDIDO]
    except ValueError:
        ids = []
    servicos = list(
        Servico.objects.select_related('profissional', 'categoria')
        .filter(pk__in=ids, profissional__is_active=True)
        .exclude(profissional_id__in=ids_com_bloqueio(request.user))
    )
    if not servicos:
        messages.error(request, 'Escolha pelo menos um profissional para pedir a visita.')
        return redirect('services:servico_list')
    if len(servicos) == 1:
        return redirect('services:servico_solicitar', pk=servicos[0].pk)
    return _processar_solicitacao(request, servicos, 'services/solicitar_varios.html')


def _distancia_para_solicitacao(solicitacao, perfil_cliente, profissional):
    """Distância (km) do profissional até o local do pedido: usa o GPS
    enviado no pedido, se houver; senão, o CEP cadastrado pelo cliente."""
    perfil_prof = getattr(profissional, 'profile', None)
    if not perfil_prof or not perfil_prof.tem_localizacao:
        return None
    if solicitacao.tem_gps:
        origem = (solicitacao.latitude, solicitacao.longitude)
    elif perfil_cliente and perfil_cliente.tem_localizacao:
        origem = (perfil_cliente.latitude, perfil_cliente.longitude)
    else:
        return None
    return calcular_distancia_km(origem[0], origem[1], perfil_prof.latitude, perfil_prof.longitude)


@user_required
def comparar_pedido(request, grupo):
    """Compara, lado a lado, as respostas dos profissionais a um pedido feito
    para vários de uma vez."""
    solicitacoes = list(
        SolicitacaoServico.objects.filter(usuario=request.user, grupo=grupo)
        .select_related('servico', 'servico__profissional', 'servico__profissional__profile', 'servico__categoria')
        .prefetch_related('anexos')
    )
    if not solicitacoes:
        raise Http404

    perfil_usuario = getattr(request.user, 'profile', None)
    medias = {
        linha['profissional']: linha
        for linha in Avaliacao.objects.filter(
            profissional__in=[sol.servico.profissional_id for sol in solicitacoes],
        ).values('profissional').annotate(media=Avg('estrelas'), total=Count('id'))
    }
    for sol in solicitacoes:
        prof = sol.servico.profissional
        info = medias.get(prof.pk)
        sol.avaliacao_media = info['media'] if info else None
        sol.total_avaliacoes = info['total'] if info else 0
        sol.avaliacao_estrelas = estrelas_da_media(sol.avaliacao_media)
        sol.orcamento_obj = getattr(sol, 'orcamento', None)
        sol.distancia_km = _distancia_para_solicitacao(sol, perfil_usuario, prof)
        sol.pode_escolher = sol.status in (
            SolicitacaoServico.STATUS_PENDENTE, SolicitacaoServico.STATUS_CONFIRMADO,
        ) and not sol.visita_concluida_em

    return render(request, 'services/comparar_pedido.html', {
        'solicitacoes': solicitacoes,
        'primeira': solicitacoes[0],
    })


@user_required
@require_POST
def escolher_profissional_pedido(request, pk):
    """Depois de comparar, o cliente fecha com um profissional: os outros
    pedidos do mesmo grupo que ainda estavam em aberto são cancelados."""
    escolhida = get_object_or_404(
        SolicitacaoServico, pk=pk, usuario=request.user, grupo__isnull=False,
        status__in=[SolicitacaoServico.STATUS_PENDENTE, SolicitacaoServico.STATUS_CONFIRMADO],
    )
    cancelados = SolicitacaoServico.objects.filter(
        usuario=request.user, grupo=escolhida.grupo,
        status__in=[SolicitacaoServico.STATUS_PENDENTE, SolicitacaoServico.STATUS_CONFIRMADO],
        visita_concluida_em__isnull=True,
    ).exclude(pk=escolhida.pk).update(status=SolicitacaoServico.STATUS_CANCELADO)
    nome = escolhida.servico.profissional.get_full_name() or escolhida.servico.profissional.username
    if cancelados:
        messages.success(request, f'Você escolheu {nome}. Os outros {cancelados} pedido(s) em aberto foram cancelados.')
    else:
        messages.success(request, f'Você escolheu {nome}.')
    if escolhida.status == SolicitacaoServico.STATUS_CONFIRMADO:
        return redirect('services:conversa_solicitacao', pk=escolhida.pk)
    return redirect('services:comparar_pedido', grupo=escolhida.grupo)


@user_required
def minhas_solicitacoes(request):
    """Lista as solicitações feitas pelo usuário logado.

    Concluídas e canceladas somem daqui sozinhas (não faz sentido o
    cliente continuar vendo pedidos já encerrados na lista principal) -
    os dados continuam existindo normalmente (orçamento, avaliação,
    pagamento), só não aparecem mais nesta tela."""
    solicitacoes = SolicitacaoServico.objects.filter(usuario=request.user).exclude(
        status__in=[SolicitacaoServico.STATUS_CONCLUIDO, SolicitacaoServico.STATUS_CANCELADO],
    ).select_related('servico').prefetch_related('anexos')
    return render(request, 'services/minhas_solicitacoes.html', {'solicitacoes': solicitacoes})


def _conversas_do_usuario(user):
    """Solicitações que aparecem na lista de conversas do usuário logado.

    Depois que o cliente conclui a visita E avalia o profissional, a
    conversa some da tela de ambos - não faz mais sentido continuar
    vendo algo já encerrado e avaliado, nem para o profissional nem
    para o cliente."""
    return SolicitacaoServico.objects.filter(
        Q(usuario=user) | Q(servico__profissional=user),
        status__in=[SolicitacaoServico.STATUS_CONFIRMADO, SolicitacaoServico.STATUS_CONCLUIDO],
    ).exclude(
        status=SolicitacaoServico.STATUS_CONCLUIDO,
        avaliacao__isnull=False,
    )


@login_required
def mensagens(request):
    """Lista de conversas (estilo WhatsApp). No celular, tocar numa pessoa
    abre a conversa com ela; no computador a página manda direto para a
    conversa mais recente (tela dividida: lista + chat), ver mensagens.html."""
    conversas = montar_lista_conversas(request.user)
    return render(request, 'services/mensagens.html', {
        'conversas': conversas,
        'primeira_conversa': conversas[0] if conversas else None,
        'total_nao_lidas': sum(1 for c in conversas if c.total_nao_lidas),
    })


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
        form = ServicoForm(request.POST, user=request.user)
        if form.is_valid():
            servico = form.save(commit=False)
            servico.profissional = request.user
            servico.save()  # P8 - Salvar serviço -> grava em D1
            messages.success(request, 'Serviço cadastrado com sucesso!')
            return redirect('services:meus_servicos')
    else:
        form = ServicoForm(user=request.user)
    return render(request, 'services/servico_form.html', {'form': form, 'modo': 'criar'})


@professional_required
def servico_criar_em_lote(request):
    """Cria automaticamente um card de serviço para cada subserviço de um
    "Serviço" (grupo) inteiro - ex.: escolher Elétrica + "Iluminação" cria
    de uma vez um Servico para cada subserviço desse grupo, todos com o
    mesmo preço e duração informados. Serviços que o profissional já
    tiver cadastrado para aquele subserviço são simplesmente pulados
    (evita duplicar)."""
    if request.method == 'POST':
        form = ServicoEmLoteForm(request.POST, user=request.user)
        if form.is_valid():
            categoria = form.cleaned_data['categoria']
            grupo = form.cleaned_data['servico']
            preco_min = form.cleaned_data['preco_min']
            preco_max = form.cleaned_data['preco_max']
            duracao_minutos = form.cleaned_data['duracao_minutos']

            dados_categoria = CATALOGO_SERVICOS.get(categoria.slug) or {}
            nome_profissao = dados_categoria.get('servico', '')
            itens_do_grupo = [
                sub for sub in dados_categoria.get('subservicos', [])
                if sub.get('grupo') == grupo
            ]

            ja_cadastrados = set(Servico.objects.filter(
                profissional=request.user, categoria=categoria,
            ).values_list('subservico', flat=True))

            novos_servicos = [
                Servico(
                    profissional=request.user,
                    categoria=categoria,
                    nome=nome_profissao,
                    subservico=sub['nome'],
                    descricao=sub['observacao'],
                    preco_min=preco_min,
                    preco_max=preco_max,
                    duracao_minutos=duracao_minutos,
                )
                for sub in itens_do_grupo
                if sub['nome'] not in ja_cadastrados
            ]
            Servico.objects.bulk_create(novos_servicos)

            pulados = len(itens_do_grupo) - len(novos_servicos)
            if novos_servicos:
                mensagem = f'{len(novos_servicos)} serviço(s) criado(s) a partir de "{grupo}".'
                if pulados:
                    mensagem += f' {pulados} já estavam cadastrados e foram mantidos como estavam.'
                messages.success(request, mensagem)
            else:
                messages.info(request, f'Você já tinha todos os serviços de "{grupo}" cadastrados.')
            return redirect('services:meus_servicos')
    else:
        form = ServicoEmLoteForm(user=request.user)
    return render(request, 'services/servico_form_lote.html', {'form': form})


@professional_required
def servico_editar(request, pk):
    servico = get_object_or_404(Servico, pk=pk, profissional=request.user)
    if request.method == 'POST':
        form = ServicoForm(request.POST, instance=servico, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Serviço atualizado com sucesso!')
            return redirect('services:meus_servicos')
    else:
        form = ServicoForm(instance=servico, user=request.user)
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
    """
    Solicitações pendentes para os serviços do profissional logado.

    Mostra só as solicitações aguardando decisão (pendente): ao aceitar, o
    profissional já é levado direto para a conversa; ao recusar, a
    solicitação sai desta lista e some, junto com os dados do cliente.

    Em vez de expor o endereço do cliente, mostra a distância aproximada
    (em km) entre o profissional e o cliente, calculada a partir das
    coordenadas obtidas via CEP de ambos (mesma cadeia de APIs usada na
    listagem de serviços: ViaCEP + AwesomeAPI/Nominatim).
    """
    solicitacoes = SolicitacaoServico.objects.filter(
        servico__profissional=request.user,
        status=SolicitacaoServico.STATUS_PENDENTE,
    ).select_related('servico', 'usuario', 'usuario__profile').prefetch_related('anexos').order_by('-urgente', 'data_visita', '-criado_em')

    perfil_profissional = getattr(request.user, 'profile', None)
    profissional_tem_localizacao = bool(perfil_profissional and perfil_profissional.tem_localizacao)

    for solicitacao in solicitacoes:
        solicitacao.distancia_km = _distancia_para_solicitacao(
            solicitacao, getattr(solicitacao.usuario, 'profile', None), request.user,
        )

    return render(request, 'services/solicitacoes_recebidas.html', {
        'solicitacoes': solicitacoes,
        'profissional_tem_localizacao': profissional_tem_localizacao,
    })


@professional_required
@require_POST
def atualizar_status_solicitacao(request, pk, acao):
    solicitacao = get_object_or_404(
        SolicitacaoServico.objects.select_related('servico', 'usuario'),
        pk=pk,
        servico__profissional=request.user,
        status=SolicitacaoServico.STATUS_PENDENTE,
    )

    destino_recusa = request.POST.get('next', '')
    if not destino_recusa.startswith('/') or destino_recusa.startswith('//'):
        destino_recusa = reverse('services:solicitacoes_recebidas')

    if acao == 'aceitar':
        solicitacao.status = SolicitacaoServico.STATUS_CONFIRMADO
        solicitacao.respondida_em = timezone.now()
        solicitacao.save(update_fields=['status', 'respondida_em'])
        notificar(
            solicitacao.usuario, 'Visita aceita!',
            f'{nome_de(request.user)} aceitou {solicitacao.servico.nome} para '
            f'{solicitacao.data_visita:%d/%m} ({solicitacao.turno_curto}). Converse por aqui.',
            url=reverse('services:conversa_solicitacao', args=[solicitacao.pk]), tipo='pedido_aceito',
            chave=f'pedido-aceito-{solicitacao.pk}',
        )
        messages.success(
            request,
            'Visita aceita! O dia combinado foi confirmado, converse com o cliente por aqui.',
        )
        return redirect('services:conversa_solicitacao', pk=solicitacao.pk)
    elif acao == 'recusar':
        solicitacao.status = SolicitacaoServico.STATUS_CANCELADO
        solicitacao.respondida_em = timezone.now()
        mensagem = 'Solicitação recusada.'
        notificar(
            solicitacao.usuario, 'Pedido recusado',
            f'{nome_de(request.user)} não poderá atender {solicitacao.servico.nome} nessa data.',
            url=reverse('services:minhas_solicitacoes'), tipo='pedido_recusado',
            chave=f'pedido-recusado-{solicitacao.pk}',
        )
    else:
        messages.error(request, 'Ação de solicitação inválida.')
        return redirect('services:solicitacoes_recebidas')

    solicitacao.save(update_fields=['status', 'respondida_em'])
    messages.success(request, mensagem)
    return redirect(destino_recusa)


def montar_lista_conversas(user):
    """Conversas do usuário já preparadas para a lista lateral (estilo
    WhatsApp): quem é o "contato" (a outra pessoa), a última mensagem e
    quantas ainda não foram lidas por quem está olhando a tela."""
    conversas = list(_select_related_conversa(_conversas_do_usuario(user)).order_by('-criado_em'))
    for conversa in conversas:
        conversa.contato = (
            conversa.usuario if user == conversa.servico.profissional
            else conversa.servico.profissional
        )
        conversa.ultima_mensagem = conversa.mensagens.select_related('autor').order_by('-criada_em').first()
        conversa.total_nao_lidas = conversa.mensagens.filter(lida=False).exclude(autor=user).count()
    # As com mensagem mais recente primeiro (como no WhatsApp).
    conversas.sort(key=lambda c: c.ultima_mensagem.criada_em if c.ultima_mensagem else c.criado_em, reverse=True)
    return conversas


def _select_related_conversa(queryset):
    return queryset.select_related(
        'servico', 'usuario', 'usuario__profile',
        'servico__profissional', 'servico__profissional__profile',
    )


@login_required
def conversa_solicitacao(request, pk):
    solicitacao = get_object_or_404(
        _select_related_conversa(SolicitacaoServico.objects),
        pk=pk,
        status__in=[SolicitacaoServico.STATUS_CONFIRMADO, SolicitacaoServico.STATUS_CONCLUIDO],
    )
    if request.user not in (solicitacao.usuario, solicitacao.servico.profissional):
        messages.error(request, 'Você não tem acesso a esta conversa.')
        return redirect('home')

    if (
        solicitacao.status == SolicitacaoServico.STATUS_CONCLUIDO
        and hasattr(solicitacao, 'avaliacao')
    ):
        messages.info(request, 'Esta conversa foi concluída e avaliada.')
        return redirect('services:mensagens')

    solicitacao.mensagens.filter(lida=False).exclude(autor=request.user).update(lida=True)
    mensagens = solicitacao.mensagens.select_related('autor').all()
    conversas = montar_lista_conversas(request.user)

    contato = solicitacao.usuario if request.user == solicitacao.servico.profissional else solicitacao.servico.profissional

    eh_profissional = request.user == solicitacao.servico.profissional

    bloqueado = existe_bloqueio(request.user, contato)

    if request.method == 'POST' and solicitacao.status == SolicitacaoServico.STATUS_CONFIRMADO:
        form = MensagemSolicitacaoForm(request.POST, request.FILES)
        via_fetch = request.headers.get('x-requested-with') == 'fetch'
        if bloqueado:
            aviso = 'Não é possível enviar mensagens: há um bloqueio entre vocês.'
            if via_fetch:
                return JsonResponse({'ok': False, 'erros': [aviso]}, status=403)
            messages.error(request, aviso)
            return redirect('services:conversa_solicitacao', pk=solicitacao.pk)
        if form.is_valid():
            mensagem = form.save(commit=False)
            mensagem.solicitacao = solicitacao
            mensagem.autor = request.user
            mensagem.tipo = form.tipo_da_mensagem()
            mensagem.save()
            if via_fetch:
                return JsonResponse({'ok': True, 'id': mensagem.pk})
            return redirect('services:conversa_solicitacao', pk=solicitacao.pk)
        if via_fetch:
            erros = [str(e) for lista in form.errors.values() for e in lista]
            return JsonResponse({'ok': False, 'erros': erros}, status=400)
    else:
        form = MensagemSolicitacaoForm()

    visita_hoje = regras.visita_de_hoje(solicitacao) if eh_profissional else None
    proposta_pendente = solicitacao.propostas_reagendamento.filter(status='pendente').select_related('proposto_por').first()

    return render(request, 'services/conversa_solicitacao.html', {
        'solicitacao': solicitacao,
        'contato': contato,
        'mensagens': mensagens,
        'conversas': conversas,
        'form': form,
        'bloqueado': bloqueado,
        'eh_profissional': eh_profissional,
        'visita_hoje': visita_hoje,
        'proposta_pendente': proposta_pendente,
        'pode_cancelar': regras.avaliar_cancelamento(solicitacao).pode,
        'visitas_agendadas': regras.visitas_da_solicitacao(solicitacao),
        'a_caminho_aviso': next((v for v in regras.visitas_da_solicitacao(solicitacao) if v.a_caminho_em and v.data == timezone.localdate()), None),
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
    if pagamentos.habilitado():
        retido = solicitacao.pagamentos.filter(status='retido').first()
        if retido:
            try:
                pagamentos.liberar_pagamento(retido)
            except pagamentos.PagamentoIndisponivel as exc:
                messages.warning(request, str(exc))
    messages.success(request, 'Serviço concluído com sucesso.')
    return redirect('services:orcamento_detalhe', pk=solicitacao.pk)


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
    return redirect('services:orcamento_detalhe', pk=pk)


# ---------------------------------------------------------------------------
# Orçamentos: valor real do serviço + dias de visita, enviados pelo
# profissional depois de conhecer o problema de perto na primeira visita.
# ---------------------------------------------------------------------------

@login_required
@require_POST
def marcar_visita_concluida(request, pk):
    """Cliente confirma, no chat, que o profissional já foi até a casa
    dele. Esse é o gatilho que libera a aba Orçamentos (no menu e na
    listagem) para esta solicitação."""
    solicitacao = get_object_or_404(
        SolicitacaoServico,
        pk=pk,
        usuario=request.user,
        status=SolicitacaoServico.STATUS_CONFIRMADO,
    )
    if not solicitacao.visita_concluida_em:
        solicitacao.visita_concluida_em = timezone.now()
        solicitacao.save(update_fields=['visita_concluida_em'])
    return redirect('services:orcamento_detalhe', pk=solicitacao.pk)


def _select_related_orcamento(queryset):
    return queryset.select_related(
        'servico', 'usuario', 'servico__profissional', 'orcamento',
    )


@login_required
def orcamentos_lista(request):
    """Lista, para o profissional, as solicitações que precisam de um
    orçamento (e o status de cada uma); para o cliente, lista os
    orçamentos das suas próprias solicitações. Só mostra solicitações
    ainda ativas: assim que o serviço é marcado como concluído, ele sai
    desta lista (e, se não sobrar nenhuma outra, a própria aba some do
    menu - ver `notificacoes_mensagens` no context_processors)."""
    base_qs = _select_related_orcamento(SolicitacaoServico.objects.filter(
        status=SolicitacaoServico.STATUS_CONFIRMADO,
        visita_concluida_em__isnull=False,
    ))

    perfil = getattr(request.user, 'profile', None)
    if perfil and perfil.is_profissional:
        solicitacoes = base_qs.filter(servico__profissional=request.user).order_by('-criado_em')
    else:
        solicitacoes = base_qs.filter(usuario=request.user).order_by('-criado_em')

    return render(request, 'services/orcamentos_lista.html', {'solicitacoes': solicitacoes})


@login_required
def orcamento_detalhe(request, pk):
    """Tela do cliente com o valor real do orçamento e os dias de visita
    definidos pelo profissional, além do botão que encerra a solicitação
    depois que o serviço estiver todo concluído. Quando o cliente conclui
    o serviço por aqui, esta mesma tela também assume o aviso gigante
    "SERVIÇO CONCLUÍDO" (com a avaliação do profissional) que antes ficava
    na aba Mensagens."""
    solicitacao = get_object_or_404(
        SolicitacaoServico.objects.select_related('servico', 'usuario', 'servico__profissional'),
        pk=pk,
        status__in=[SolicitacaoServico.STATUS_CONFIRMADO, SolicitacaoServico.STATUS_CONCLUIDO],
    )
    if request.user not in (solicitacao.usuario, solicitacao.servico.profissional):
        messages.error(request, 'Você não tem acesso a este orçamento.')
        return redirect('home')

    orcamento = getattr(solicitacao, 'orcamento', None)
    dias_visita = orcamento.dias_visita.all() if orcamento else []

    if orcamento and request.user == solicitacao.usuario and not orcamento.visualizado_pelo_cliente:
        orcamento.visualizado_pelo_cliente = True
        orcamento.save(update_fields=['visualizado_pelo_cliente'])

    avaliacao = None
    avaliacao_form = None
    outros_orcamentos_pendentes = False
    if solicitacao.status == SolicitacaoServico.STATUS_CONCLUIDO and request.user == solicitacao.usuario:
        avaliacao = getattr(solicitacao, 'avaliacao', None)
        avaliacao_form = AvaliacaoForm(instance=avaliacao)
        outros_orcamentos_pendentes = SolicitacaoServico.objects.filter(
            usuario=request.user,
            status=SolicitacaoServico.STATUS_CONFIRMADO,
            visita_concluida_em__isnull=False,
        ).exclude(pk=solicitacao.pk).exists()

    if orcamento and request.user == solicitacao.servico.profissional and not orcamento.resposta_vista_pelo_profissional:
        orcamento.resposta_vista_pelo_profissional = True
        orcamento.save(update_fields=['resposta_vista_pelo_profissional'])

    return render(request, 'services/orcamento_detalhe.html', {
        'hoje_data': timezone.localdate(),
        'pix_habilitado': pagamentos.habilitado(),
        'pagamento': pagamentos.pagamento_ativo(solicitacao) if orcamento else None,
        'visitas_agendadas': regras.visitas_da_solicitacao(solicitacao) if orcamento else [],
        'solicitacao': solicitacao,
        'orcamento': orcamento,
        'dias_visita': dias_visita,
        'avaliacao': avaliacao,
        'avaliacao_form': avaliacao_form,
        'outros_orcamentos_pendentes': outros_orcamentos_pendentes,
    })


@professional_required
def orcamento_editar(request, pk):
    """Profissional preenche (ou atualiza) o valor real do orçamento e os
    dias de visita necessários para concluir o serviço."""
    solicitacao = get_object_or_404(
        SolicitacaoServico,
        pk=pk,
        servico__profissional=request.user,
        status__in=[SolicitacaoServico.STATUS_CONFIRMADO, SolicitacaoServico.STATUS_CONCLUIDO],
    )
    orcamento = getattr(solicitacao, 'orcamento', None)
    dias_existentes = orcamento.dias_visita.all() if orcamento else DiaVisitaOrcamento.objects.none()

    if orcamento and pagamentos.pagamento_ativo(solicitacao):
        messages.error(
            request,
            'Este orçamento já tem um pagamento em andamento e não pode mais ser alterado. '
            'Combine ajustes de data pelo chat (reagendar).',
        )
        return redirect('services:orcamentos_lista')

    if request.method == 'POST':
        form = OrcamentoForm(request.POST, instance=orcamento)
        formset = DiaVisitaFormSet(request.POST, queryset=dias_existentes, prefix='dias')
        if form.is_valid() and formset.is_valid():
            orcamento = form.save(commit=False)
            orcamento.solicitacao = solicitacao
            # Toda vez que o profissional envia/atualiza o orçamento, ele
            # volta a valer como "novo" para o cliente, disparando de novo
            # o aviso vermelho no menu Orçamentos.
            orcamento.visualizado_pelo_cliente = False
            # Toda proposta nova (ou alterada) precisa ser aprovada de novo.
            orcamento.status = Orcamento.STATUS_PENDENTE
            orcamento.respondido_em = None
            orcamento.motivo_recusa = ''
            orcamento.save()

            dias = formset.save(commit=False)
            for dia in dias:
                dia.orcamento = orcamento
                dia.status = _DiaVisitaOrcamento.STATUS_PROPOSTA
                dia.save()
            for dia in formset.deleted_objects:
                dia.delete()
            orcamento.dias_visita.exclude(status=_DiaVisitaOrcamento.STATUS_PROPOSTA).update(
                status=_DiaVisitaOrcamento.STATUS_PROPOSTA,
            )
            notificar(
                solicitacao.usuario, 'Novo orçamento para aprovar',
                f'{nome_de(request.user)} enviou o orçamento de {solicitacao.servico.nome}: R$ {orcamento.valor}.',
                url=reverse('services:orcamento_detalhe', args=[solicitacao.pk]), tipo='orcamento',
                chave=f'orcamento-enviado-{orcamento.pk}-{int(timezone.now().timestamp())}',
            )

            messages.success(request, 'Orçamento enviado ao cliente com sucesso.')
            return redirect('services:orcamentos_lista')
    else:
        form = OrcamentoForm(instance=orcamento)
        formset = DiaVisitaFormSet(queryset=dias_existentes, prefix='dias')

    return render(request, 'services/orcamento_form.html', {
        'solicitacao': solicitacao,
        'form': form,
        'formset': formset,
    })
