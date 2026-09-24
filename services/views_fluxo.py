"""Telas e ações do fluxo "combinar e fechar o serviço":
notificações, aprovação do orçamento, "estou a caminho", cancelamento,
reagendamento e pagamento por Pix."""
import hmac  # noqa: F401  (usado pelos provedores reais ao validar webhooks)

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.decorators import professional_required, user_required

from . import pagamentos, regras
from .models import (
    DiaVisitaOrcamento, Notificacao, Orcamento, Pagamento, PropostaReagendamento, SolicitacaoServico,
)
from .notificacoes import nome_de, notificar


def _participante(request, pk, **filtros):
    """Solicitação da qual o usuário logado é cliente ou profissional."""
    solicitacao = get_object_or_404(
        SolicitacaoServico.objects.select_related('usuario', 'servico', 'servico__profissional'),
        pk=pk, **filtros,
    )
    if request.user not in (solicitacao.usuario, solicitacao.servico.profissional):
        raise Http404
    return solicitacao


def _outra_parte(solicitacao, usuario):
    return solicitacao.servico.profissional if usuario == solicitacao.usuario else solicitacao.usuario


def _url_conversa(solicitacao):
    return reverse('services:conversa_solicitacao', args=[solicitacao.pk])


def _proximo(request, padrao):
    destino = request.POST.get('next') or request.GET.get('next')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return destino
    return padrao


# ------------------------------------------------------------------ notificações

@login_required
def notificacao_abrir(request, pk):
    notificacao = get_object_or_404(Notificacao, pk=pk, usuario=request.user)
    if not notificacao.lida:
        notificacao.lida = True
        notificacao.save(update_fields=['lida'])
    destino = notificacao.url if notificacao.url.startswith('/') else reverse('home')
    return redirect(destino)


@login_required
@require_POST
def notificacoes_lidas(request):
    Notificacao.objects.filter(usuario=request.user, lida=False).update(lida=True)
    return redirect(_proximo(request, reverse('home')))


# ------------------------------------------------------------------ orçamento

@user_required
@require_POST
def orcamento_responder(request, pk, acao):
    """O cliente aprova ou recusa o orçamento. Ao aprovar, as visitas
    previstas no orçamento entram na agenda automaticamente."""
    solicitacao = get_object_or_404(
        SolicitacaoServico.objects.select_related('servico', 'servico__profissional'),
        pk=pk, usuario=request.user, status=SolicitacaoServico.STATUS_CONFIRMADO,
    )
    orcamento = getattr(solicitacao, 'orcamento', None)
    if not orcamento or orcamento.status != Orcamento.STATUS_PENDENTE:
        messages.error(request, 'Não há orçamento aguardando a sua resposta.')
        return redirect('services:orcamento_detalhe', pk=solicitacao.pk)

    profissional = solicitacao.servico.profissional
    url = reverse('services:orcamento_detalhe', args=[solicitacao.pk])

    if acao == 'aprovar':
        with transaction.atomic():
            orcamento.status = Orcamento.STATUS_APROVADO
            orcamento.respondido_em = timezone.now()
            orcamento.motivo_recusa = ''
            orcamento.resposta_vista_pelo_profissional = False
            orcamento.save(update_fields=['status', 'respondido_em', 'motivo_recusa', 'resposta_vista_pelo_profissional'])
            dias = list(orcamento.dias_visita.exclude(status=DiaVisitaOrcamento.STATUS_CANCELADA))
            for dia in dias:
                dia.status = DiaVisitaOrcamento.STATUS_AGENDADA
                dia.turno = solicitacao.turno
                dia.save(update_fields=['status', 'turno'])
        datas = ', '.join(d.data.strftime('%d/%m') for d in dias)
        notificar(
            profissional, 'Orçamento aprovado!',
            f'{nome_de(request.user)} aprovou R$ {orcamento.valor}.'
            + (f' Visitas agendadas: {datas}.' if dias else ''),
            url=url, tipo='orcamento', chave=f'orcamento-aprovado-{orcamento.pk}-{int(orcamento.respondido_em.timestamp())}',
        )
        messages.success(
            request,
            'Orçamento aprovado!' + (f' {len(dias)} visita(s) já estão na agenda.' if dias else ''),
        )
    elif acao == 'recusar':
        orcamento.status = Orcamento.STATUS_RECUSADO
        orcamento.respondido_em = timezone.now()
        orcamento.motivo_recusa = request.POST.get('motivo', '').strip()[:500]
        orcamento.resposta_vista_pelo_profissional = False
        orcamento.save(update_fields=['status', 'respondido_em', 'motivo_recusa', 'resposta_vista_pelo_profissional'])
        notificar(
            profissional, 'Orçamento recusado',
            f'{nome_de(request.user)} recusou o orçamento.'
            + (f' Motivo: {orcamento.motivo_recusa}' if orcamento.motivo_recusa else ' Converse para ajustar o valor.'),
            url=url, tipo='orcamento', chave=f'orcamento-recusado-{orcamento.pk}-{int(orcamento.respondido_em.timestamp())}',
        )
        messages.success(request, 'Orçamento recusado. O profissional foi avisado e pode enviar uma nova proposta.')
    else:
        raise Http404
    return redirect('services:orcamento_detalhe', pk=solicitacao.pk)


# ------------------------------------------------------------------ a caminho

@professional_required
@require_POST
def estou_a_caminho(request, pk, chave):
    solicitacao = get_object_or_404(
        SolicitacaoServico.objects.select_related('usuario', 'servico'),
        pk=pk, servico__profissional=request.user, status=SolicitacaoServico.STATUS_CONFIRMADO,
    )
    visita = regras.visita_por_chave(solicitacao, chave)
    destino = _proximo(request, _url_conversa(solicitacao))
    if not visita or visita.data != timezone.localdate():
        messages.error(request, 'O aviso "estou a caminho" só pode ser enviado no dia da visita.')
        return redirect(destino)
    if visita.a_caminho_em:
        messages.info(request, 'O cliente já foi avisado de que você está a caminho.')
        return redirect(destino)

    agora = timezone.now()
    visita.obj.a_caminho_em = agora
    visita.obj.save(update_fields=['a_caminho_em'])
    notificar(
        solicitacao.usuario, f'{nome_de(request.user)} está a caminho',
        f'Visita de {solicitacao.servico.nome}. Avisado às {timezone.localtime(agora):%H:%M}.',
        url=_url_conversa(solicitacao), tipo='a_caminho', chave=f'a-caminho-{visita.chave}-{visita.data.isoformat()}',
    )
    messages.success(request, 'Pronto, o cliente foi avisado que você está a caminho.')
    return redirect(destino)


# ------------------------------------------------------------------ cancelamento

class CancelamentoForm(forms.Form):
    motivo = forms.CharField(
        required=False, max_length=500, label='Motivo (opcional)',
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Conte rapidamente o que aconteceu'}),
    )


@login_required
def cancelar_solicitacao(request, pk):
    solicitacao = _participante(request, pk)
    avaliacao = regras.avaliar_cancelamento(solicitacao)
    perfil = getattr(request.user, 'profile', None)
    eh_profissional = bool(perfil and perfil.is_profissional)

    # Profissional só "recusa" pedidos pendentes (tela própria).
    if eh_profissional and solicitacao.status == SolicitacaoServico.STATUS_PENDENTE:
        return redirect('services:solicitacoes_recebidas')

    if request.method == 'POST' and avaliacao.pode:
        form = CancelamentoForm(request.POST)
        if form.is_valid():
            solicitacao.status = SolicitacaoServico.STATUS_CANCELADO
            solicitacao.cancelado_por = request.user
            solicitacao.cancelado_em = timezone.now()
            solicitacao.cancelamento_tardio = avaliacao.tardio
            solicitacao.motivo_cancelamento = form.cleaned_data['motivo']
            solicitacao.save(update_fields=[
                'status', 'cancelado_por', 'cancelado_em', 'cancelamento_tardio', 'motivo_cancelamento',
            ])
            solicitacao.propostas_reagendamento.filter(
                status=PropostaReagendamento.STATUS_PENDENTE,
            ).update(status=PropostaReagendamento.STATUS_CANCELADA)
            outra = _outra_parte(solicitacao, request.user)
            notificar(
                outra, 'Visita cancelada' + (' (em cima da hora)' if avaliacao.tardio else ''),
                f'{nome_de(request.user)} cancelou o pedido de {solicitacao.servico.nome}.'
                + (f' Motivo: {solicitacao.motivo_cancelamento}' if solicitacao.motivo_cancelamento else ''),
                url=reverse('services:minhas_solicitacoes') if outra == solicitacao.usuario
                else reverse('services:solicitacoes_recebidas'),
                tipo='cancelamento', chave=f'cancelado-{solicitacao.pk}',
            )
            messages.success(request, 'Pedido cancelado. A outra pessoa foi avisada.')
            return redirect('services:minhas_solicitacoes' if not eh_profissional else 'services:solicitacoes_recebidas')
    else:
        form = CancelamentoForm()

    return render(request, 'services/cancelar_solicitacao.html', {
        'solicitacao': solicitacao,
        'avaliacao': avaliacao,
        'form': form,
        'regras': regras.regras_em_texto()['cancelamento'],
        'contato': _outra_parte(solicitacao, request.user),
    })


# ------------------------------------------------------------------ reagendamento

class ReagendamentoForm(forms.Form):
    visita = forms.ChoiceField(label='Qual visita?', widget=forms.RadioSelect)
    nova_data = forms.DateField(label='Nova data', widget=forms.DateInput(attrs={'type': 'date'}))
    novo_turno = forms.ChoiceField(
        label='Novo horário', choices=SolicitacaoServico.TURNO_CHOICES, initial=SolicitacaoServico.TURNO_QUALQUER,
        widget=forms.RadioSelect,
    )
    motivo = forms.CharField(required=False, max_length=255, label='Motivo (opcional)')

    def __init__(self, *args, visitas=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.visitas = {v.chave: v for v in visitas}
        self.fields['visita'].choices = [(v.chave, v.rotulo) for v in visitas]
        if len(visitas) == 1:
            self.fields['visita'].initial = visitas[0].chave

    def clean(self):
        dados = super().clean()
        visita = self.visitas.get(dados.get('visita'))
        nova_data = dados.get('nova_data')
        if visita and nova_data:
            pode, bloqueio = regras.avaliar_reagendamento(visita)
            if not pode:
                raise forms.ValidationError(bloqueio)
            if nova_data < timezone.localdate():
                self.add_error('nova_data', 'Escolha uma data de hoje em diante.')
            elif (nova_data, dados.get('novo_turno')) == (visita.data, visita.turno):
                raise forms.ValidationError('A nova data e horário são iguais aos atuais.')
        return dados


@login_required
def reagendar(request, pk):
    solicitacao = _participante(request, pk, status=SolicitacaoServico.STATUS_CONFIRMADO)
    visitas = regras.visitas_da_solicitacao(solicitacao)
    pendente = solicitacao.propostas_reagendamento.filter(status=PropostaReagendamento.STATUS_PENDENTE).first()

    if pendente:
        messages.info(request, 'Já existe uma proposta de reagendamento aguardando resposta neste pedido.')
        return redirect(_url_conversa(solicitacao))
    if not visitas:
        messages.info(request, 'Não há visitas futuras para reagendar neste pedido.')
        return redirect(_url_conversa(solicitacao))

    if request.method == 'POST':
        form = ReagendamentoForm(request.POST, visitas=visitas)
        if form.is_valid():
            visita = form.visitas[form.cleaned_data['visita']]
            proposta = PropostaReagendamento.objects.create(
                solicitacao=solicitacao,
                dia_visita=visita.obj if visita.tipo == 'dia' else None,
                proposto_por=request.user,
                nova_data=form.cleaned_data['nova_data'],
                novo_turno=form.cleaned_data['novo_turno'],
                motivo=form.cleaned_data['motivo'],
                data_anterior=visita.data,
                turno_anterior=visita.turno,
            )
            notificar(
                _outra_parte(solicitacao, request.user), 'Pedido de reagendamento',
                f'{nome_de(request.user)} quer mudar a visita de {visita.data:%d/%m} para '
                f'{proposta.nova_data:%d/%m} ({proposta.turno_novo_curto}). Responda para confirmar.',
                url=_url_conversa(solicitacao), tipo='reagendamento', chave=f'reagendar-{proposta.pk}',
            )
            messages.success(request, 'Proposta enviada. A visita só muda quando a outra pessoa aceitar.')
            return redirect(_url_conversa(solicitacao))
    else:
        form = ReagendamentoForm(visitas=visitas)

    return render(request, 'services/reagendar.html', {
        'solicitacao': solicitacao,
        'form': form,
        'regras': regras.regras_em_texto()['reagendamento'],
        'contato': _outra_parte(solicitacao, request.user),
        'hoje_iso': timezone.localdate().isoformat(),
    })


@login_required
@require_POST
def responder_reagendamento(request, pk, acao):
    proposta = get_object_or_404(
        PropostaReagendamento.objects.select_related(
            'solicitacao', 'solicitacao__usuario', 'solicitacao__servico', 'solicitacao__servico__profissional',
            'dia_visita', 'proposto_por',
        ),
        pk=pk, status=PropostaReagendamento.STATUS_PENDENTE,
        solicitacao__status=SolicitacaoServico.STATUS_CONFIRMADO,
    )
    solicitacao = proposta.solicitacao
    if request.user not in (solicitacao.usuario, solicitacao.servico.profissional):
        raise Http404
    destino = _proximo(request, _url_conversa(solicitacao))
    outra = proposta.proposto_por
    agora = timezone.now()

    if acao == 'cancelar':
        if request.user != proposta.proposto_por:
            return HttpResponseForbidden()
        proposta.status = PropostaReagendamento.STATUS_CANCELADA
        proposta.respondida_em = agora
        proposta.save(update_fields=['status', 'respondida_em'])
        messages.success(request, 'Proposta cancelada.')
        return redirect(destino)

    if request.user == proposta.proposto_por:
        return HttpResponseForbidden()

    if acao == 'aceitar':
        with transaction.atomic():
            if proposta.dia_visita_id:
                alvo = proposta.dia_visita
                alvo.data, alvo.turno = proposta.nova_data, proposta.novo_turno
                alvo.reagendamentos += 1
                alvo.a_caminho_em = None
                alvo.save(update_fields=['data', 'turno', 'reagendamentos', 'a_caminho_em'])
            else:
                solicitacao.data_visita, solicitacao.turno = proposta.nova_data, proposta.novo_turno
                solicitacao.reagendamentos += 1
                solicitacao.a_caminho_em = None
                solicitacao.urgente = solicitacao.urgente and proposta.nova_data == timezone.localdate()
                solicitacao.save(update_fields=['data_visita', 'turno', 'reagendamentos', 'a_caminho_em', 'urgente'])
            proposta.status = PropostaReagendamento.STATUS_ACEITA
            proposta.respondida_em = agora
            proposta.save(update_fields=['status', 'respondida_em'])
        notificar(
            outra, 'Reagendamento aceito',
            f'{nome_de(request.user)} aceitou: nova visita em {proposta.nova_data:%d/%m/%Y} ({proposta.turno_novo_curto}).',
            url=_url_conversa(solicitacao), tipo='reagendamento', chave=f'reagendar-aceito-{proposta.pk}',
        )
        messages.success(request, f'Visita reagendada para {proposta.nova_data:%d/%m/%Y}.')
    elif acao == 'recusar':
        proposta.status = PropostaReagendamento.STATUS_RECUSADA
        proposta.respondida_em = agora
        proposta.save(update_fields=['status', 'respondida_em'])
        notificar(
            outra, 'Reagendamento recusado',
            f'{nome_de(request.user)} não pode na nova data. Continua valendo {proposta.data_anterior:%d/%m/%Y}.',
            url=_url_conversa(solicitacao), tipo='reagendamento', chave=f'reagendar-recusado-{proposta.pk}',
        )
        messages.success(request, 'Proposta recusada. Continua valendo a data anterior.')
    else:
        raise Http404
    return redirect(destino)


# ------------------------------------------------------------------ pagamento (Pix)

def _solicitacao_do_pagamento(request, pk):
    return _participante(request, pk, status__in=[
        SolicitacaoServico.STATUS_CONFIRMADO, SolicitacaoServico.STATUS_CONCLUIDO,
    ])


@login_required
def pagamento_detalhe(request, pk):
    if not pagamentos.habilitado():
        raise Http404
    solicitacao = _solicitacao_do_pagamento(request, pk)
    return render(request, 'services/pagamento.html', {
        'solicitacao': solicitacao,
        'orcamento': getattr(solicitacao, 'orcamento', None),
        'pagamento': pagamentos.pagamento_ativo(solicitacao),
        'eh_cliente': request.user == solicitacao.usuario,
        'comissao_percentual': pagamentos.calcular_valores(100)[0],
        'modo_simulado': pagamentos.obter_gateway().nome == 'simulado',
        'chave_pix_cadastrada': bool(getattr(solicitacao.servico.profissional.profile, 'chave_pix', '')),
    })


@user_required
@require_POST
def pagamento_iniciar(request, pk):
    solicitacao = get_object_or_404(
        SolicitacaoServico.objects.select_related('usuario', 'servico', 'servico__profissional'),
        pk=pk, usuario=request.user, status=SolicitacaoServico.STATUS_CONFIRMADO,
    )
    try:
        pagamentos.iniciar_pagamento(solicitacao)
    except pagamentos.PagamentoIndisponivel as exc:
        messages.error(request, str(exc))
        return redirect('services:orcamento_detalhe', pk=solicitacao.pk)
    return redirect('services:pagamento_detalhe', pk=solicitacao.pk)


@user_required
@require_POST
def pagamento_simular(request, pk):
    """Só existe para testar o fluxo com o provedor simulado."""
    from django.conf import settings
    if not (settings.DEBUG and pagamentos.obter_gateway().nome == 'simulado' and pagamentos.habilitado()):
        raise Http404
    solicitacao = get_object_or_404(SolicitacaoServico, pk=pk, usuario=request.user)
    pagamento = pagamentos.pagamento_ativo(solicitacao)
    if pagamento:
        pagamentos.confirmar_pagamento(pagamento)
        messages.success(request, 'Pagamento simulado como recebido.')
    return redirect('services:pagamento_detalhe', pk=solicitacao.pk)


@login_required
def pagamento_status(request, pk):
    if not pagamentos.habilitado():
        raise Http404
    solicitacao = _solicitacao_do_pagamento(request, pk)
    pagamento = pagamentos.pagamento_ativo(solicitacao)
    return JsonResponse({'status': pagamento.status if pagamento else None})


@csrf_exempt
@require_POST
def webhook_pix(request, provedor):
    """Endereço que o provedor chama quando um Pix é pago."""
    if not pagamentos.habilitado():
        raise Http404
    gateway = pagamentos.obter_gateway(provedor)
    try:
        evento = gateway.ler_webhook(request)
    except (pagamentos.WebhookInvalido, pagamentos.ProvedorNaoConfigurado):
        return HttpResponseForbidden()
    if evento.pago:
        pagamento = Pagamento.objects.filter(provedor=gateway.nome, id_externo=evento.id_externo).first()
        if pagamento:
            pagamentos.confirmar_pagamento(pagamento)
    return HttpResponse('ok')
