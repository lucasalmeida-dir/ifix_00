"""Confiança e segurança: verificação de identidade, denúncia, bloqueio e
exclusão de conta (LGPD)."""
import mimetypes

from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import DenunciaForm, VerificacaoForm
from .models import Bloqueio, Denuncia, Profile
from . import seguranca


def _destino_seguro(request, padrao):
    proximo = request.POST.get('next') or request.GET.get('next') or ''
    if proximo and url_has_allowed_host_and_scheme(proximo, {request.get_host()}):
        return proximo
    return padrao


# ---------------------------------------------------------------------------
# Selo "Profissional verificado"
# ---------------------------------------------------------------------------

@login_required
def verificacao(request):
    """O profissional envia documento + foto; a equipe do IFIX analisa no
    painel administrativo e é QUEM concede o selo (o profissional nunca
    consegue se marcar como verificado)."""
    profile = get_object_or_404(Profile, user=request.user)
    if not profile.is_profissional:
        messages.error(request, 'A verificação de identidade é só para profissionais.')
        return redirect('home')

    pode_enviar = profile.verificacao_status in (Profile.VERIF_NAO_ENVIADO, Profile.VERIF_RECUSADO)
    if request.method == 'POST' and pode_enviar:
        form = VerificacaoForm(request.POST, request.FILES)
        if form.is_valid():
            antigos = [(profile.documento, profile.documento.name), (profile.foto_verificacao, profile.foto_verificacao.name)]
            profile.documento = form.cleaned_data['documento']
            profile.foto_verificacao = form.cleaned_data['foto_verificacao']
            profile.verificacao_status = Profile.VERIF_PENDENTE
            profile.verificacao_enviada_em = timezone.now()
            profile.verificacao_motivo_recusa = ''
            profile.verificado_em = None
            profile.verificado_por = None
            profile.save()
            for arquivo, nome in antigos:
                if nome and nome != arquivo.name:
                    arquivo.storage.delete(nome)
            messages.success(request, 'Documentos enviados! A equipe do IFIX vai analisar e você será avisado(a).')
            return redirect('accounts:verificacao')
    else:
        form = VerificacaoForm()

    return render(request, 'accounts/verificacao.html', {
        'profile': profile, 'form': form, 'pode_enviar': pode_enviar,
    })


@login_required
@require_POST
def decidir_verificacao(request, pk):
    """A equipe (staff com permissão) aprova ou recusa a verificação direto da
    página do profissional no site, sem precisar abrir o painel admin."""
    if not request.user.is_staff or not request.user.has_perm('accounts.change_profile'):
        raise Http404
    perfil = get_object_or_404(Profile, pk=pk, tipo=Profile.TIPO_PROFISSIONAL)
    acao = request.POST.get('acao')
    if acao == 'aprovar':
        if not (perfil.documento and perfil.foto_verificacao):
            messages.error(request, 'Este profissional ainda não enviou documento e foto.')
        else:
            seguranca.aprovar_verificacao(perfil, request.user)
            messages.success(request, 'Profissional verificado: o selo já aparece para todos.')
    elif acao == 'recusar':
        seguranca.recusar_verificacao(perfil, (request.POST.get('motivo') or '').strip()[:500])
        messages.warning(request, 'Verificação recusada. O profissional foi avisado.')
    return redirect(_destino_seguro(request, '/'))


@login_required
def arquivo_verificacao(request, pk, campo):
    """Entrega documento/foto de verificação SÓ para a equipe (staff).
    Os arquivos ficam fora de /media/, então não têm endereço público."""
    if not request.user.is_staff or not request.user.has_perm('accounts.change_profile'):
        raise Http404
    if campo not in ('documento', 'foto'):
        raise Http404
    profile = get_object_or_404(Profile, pk=pk)
    arquivo = profile.documento if campo == 'documento' else profile.foto_verificacao
    if not arquivo or not arquivo.name:
        raise Http404
    tipo = mimetypes.guess_type(arquivo.name)[0] or 'application/octet-stream'
    resposta = FileResponse(arquivo.open('rb'), content_type=tipo)
    resposta['Cache-Control'] = 'private, no-store'
    resposta['X-Content-Type-Options'] = 'nosniff'
    return resposta


# ---------------------------------------------------------------------------
# Denúncia e bloqueio
# ---------------------------------------------------------------------------

@login_required
def denunciar(request, user_id):
    denunciado = get_object_or_404(User, pk=user_id, is_active=True)
    if denunciado == request.user:
        raise Http404
    from services.models import SolicitacaoServico

    solicitacao = None
    sol_id = request.POST.get('solicitacao') or request.GET.get('solicitacao')
    if sol_id and sol_id.isdigit():
        solicitacao = SolicitacaoServico.objects.filter(pk=sol_id).select_related('servico').first()
        participantes = (
            {solicitacao.usuario_id, solicitacao.servico.profissional_id} if solicitacao else set()
        )
        if not solicitacao or {request.user.pk, denunciado.pk} != participantes:
            solicitacao = None

    destino = _destino_seguro(request, '/')
    if request.method == 'POST':
        form = DenunciaForm(request.POST)
        if form.is_valid():
            ja_aberta = Denuncia.objects.filter(
                autor=request.user, denunciado=denunciado,
                status__in=[Denuncia.STATUS_ABERTA, Denuncia.STATUS_ANALISE],
            ).exists()
            if ja_aberta:
                messages.info(request, 'Você já tem uma denúncia em análise contra esta pessoa. Nossa equipe vai avaliar.')
            else:
                denuncia = form.save(commit=False)
                denuncia.autor = request.user
                denuncia.denunciado = denunciado
                denuncia.solicitacao = solicitacao
                denuncia.save()
                messages.success(
                    request,
                    'Denúncia enviada. Nossa equipe vai analisar. Se quiser, você também pode bloquear essa pessoa.',
                )
            return redirect(destino)
    else:
        form = DenunciaForm()

    return render(request, 'accounts/denunciar.html', {
        'form': form, 'denunciado': denunciado, 'solicitacao': solicitacao, 'next': destino,
        'ja_bloqueado': Bloqueio.objects.filter(bloqueador=request.user, bloqueado=denunciado).exists(),
    })


@login_required
@require_POST
def bloquear(request, user_id):
    """Bloqueia a pessoa: ela some das buscas e não há mais pedidos nem mensagens."""
    alvo = get_object_or_404(User, pk=user_id)
    if alvo == request.user:
        raise Http404
    seguranca.bloquear(request.user, alvo)
    messages.success(
        request,
        'Pessoa bloqueada. Ela não aparece mais para você, e não é possível pedir serviço nem trocar mensagens.',
    )
    return redirect(_destino_seguro(request, '/'))


# ---------------------------------------------------------------------------
# Excluir conta (LGPD)
# ---------------------------------------------------------------------------

@login_required
def excluir_conta(request):
    """Pede a senha (ou digitar EXCLUIR, para contas criadas pelo Google,
    que não têm senha) e apaga a conta e os dados pessoais."""
    usuario = request.user
    tem_senha = usuario.has_usable_password()
    erro = ''
    if request.method == 'POST':
        if tem_senha:
            confirmado = usuario.check_password(request.POST.get('senha', ''))
            erro = '' if confirmado else 'Senha incorreta.'
        else:
            confirmado = request.POST.get('confirmacao', '').strip().upper() == 'EXCLUIR'
            erro = '' if confirmado else 'Digite EXCLUIR para confirmar.'
        if confirmado:
            if usuario.is_superuser or usuario.is_staff:
                messages.error(request, 'Contas da equipe são removidas pelo painel administrativo.')
                return redirect('accounts:profile_edit')
            resultado = seguranca.excluir_conta(usuario)
            auth_logout(request)
            messages.success(
                request,
                'Sua conta foi excluída e seus dados pessoais removidos.' if resultado == 'excluida'
                else 'Sua conta foi encerrada e seus dados pessoais removidos. Apenas registros que a lei '
                     'exige guardar (como pagamentos) permanecem, sem identificar você.',
            )
            return redirect('home')
    return render(request, 'accounts/excluir_conta.html', {'tem_senha': tem_senha, 'erro': erro})
