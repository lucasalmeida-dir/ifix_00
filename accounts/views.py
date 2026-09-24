import re

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import UserRegisterForm, ProfessionalRegisterForm, ProfileEditForm, EspecialidadeForm
from .models import Profile
from .services import CepInvalidoError, GoogleTokenInvalidoError, consultar_cep, verificar_id_token_google


def register_user(request):
    """U1 - Cadastro de usuário."""
    if request.method == 'POST':
        form = UserRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, 'Cadastro realizado com sucesso! Bem-vindo(a).')
            return redirect('home')
    else:
        form = UserRegisterForm()
    return render(request, 'accounts/register_user.html', {'form': form})


def register_professional(request):
    """P1 - Cadastro profissional."""
    if request.method == 'POST':
        form = ProfessionalRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect('accounts:escolher_especialidade')
    else:
        form = ProfessionalRegisterForm()
    return render(request, 'accounts/register_professional.html', {'form': form})


@require_POST
def google_login(request):
    """Recebe o `credential` (ID token) do botão "Entrar com Google"
    (Google Identity Services), confere com o próprio Google e loga a
    conta - criando uma conta de cliente na hora se for a primeira vez.

    Contas profissionais continuam passando pelo cadastro completo, já
    que precisam escolher especialidade e aceitar o Termo de Uso antes de
    usar o site; login rápido aqui é só para quem já é (ou vai virar)
    cliente.
    """
    proximo = request.POST.get('next', '')
    destino = proximo if url_has_allowed_host_and_scheme(proximo, {request.get_host()}) else 'home'

    try:
        dados = verificar_id_token_google(request.POST.get('credential', ''))
    except GoogleTokenInvalidoError as exc:
        messages.error(request, str(exc))
        return redirect('accounts:login')

    user = User.objects.filter(email__iexact=dados['email']).first()
    if user is not None and not hasattr(user, 'profile'):
        # Conta sem Profile (ex.: admin criado por createsuperuser) - não é
        # uma conta do site, então não deixamos logar por aqui.
        messages.error(request, 'Não foi possível entrar com esta conta Google.')
        return redirect('accounts:login')

    if user is None:
        base = re.sub(r'[^\w.@+-]', '', dados['email'].split('@')[0]) or 'usuario'
        username, sufixo = base, 1
        while User.objects.filter(username=username).exists():
            sufixo += 1
            username = f'{base}{sufixo}'
        user = User.objects.create_user(
            username=username, email=dados['email'],
            first_name=dados['nome'], last_name=dados['sobrenome'],
        )
        user.set_unusable_password()
        user.save(update_fields=['password'])
        Profile.objects.create(user=user, tipo=Profile.TIPO_USUARIO)
        messages.success(
            request,
            'Conta criada com sua conta Google! Complete telefone e CEP em '
            '"Editar perfil" quando quiser pedir uma visita.',
        )
    else:
        messages.success(request, f'Bem-vindo(a) de volta, {user.first_name or user.username}!')

    auth_login(request, user)
    return redirect(destino)


@login_required
def aceitar_termos(request):
    """Exibe o Termo de Condições de Uso e registra o aceite obrigatório.

    Exigido apenas para contas profissionais, logo após o cadastro e depois
    de escolhida a Especialidade/Área de atuação: enquanto o Profile de um
    profissional não tiver `termos_aceitos = True`, o TermosAceiteMiddleware
    redireciona qualquer outra página desta tela, impedindo o acesso ao
    restante do site.
    """
    profile = get_object_or_404(Profile, user=request.user)

    if profile.termos_aceitos:
        return redirect('home')

    if request.method == 'POST':
        if request.POST.get('aceite') == 'on':
            profile.termos_aceitos = True
            profile.termos_aceitos_em = timezone.now()
            profile.save(update_fields=['termos_aceitos', 'termos_aceitos_em'])
            messages.success(request, 'Termo de uso aceito. Seja bem-vindo(a) ao IFIX!')
            return redirect('home')
        messages.error(request, 'É necessário ler e aceitar o Termo de Condições de Uso para continuar.')

    return render(request, 'accounts/aceitar_termos.html', {'profile': profile})


@login_required
def escolher_especialidade(request):
    """P1.1 - Escolha da(s) Especialidade(s)/Área(s) de atuação.

    Exibida numa tela própria, logo depois do Cadastro profissional e
    antes do aceite do Termo de Uso: enquanto o Profile não tiver
    nenhuma `especialidades` marcada, o EspecialidadeObrigatoriaMiddleware
    redireciona qualquer outra página para cá, impedindo o acesso ao
    restante do site. O profissional pode marcar mais de uma categoria.
    """
    profile = get_object_or_404(Profile, user=request.user)

    if not profile.is_profissional or profile.especialidades.exists():
        return redirect('home')

    if request.method == 'POST':
        form = EspecialidadeForm(request.POST, instance=profile)
        selecionadas_pks = {int(pk) for pk in request.POST.getlist('especialidades') if pk.isdigit()}
        if form.is_valid():
            form.save()
            messages.success(request, 'Especialidades cadastradas com sucesso!')
            return redirect('accounts:aceitar_termos')
    else:
        form = EspecialidadeForm(instance=profile)
        selecionadas_pks = set()

    cartoes = [
        {'categoria': categoria, 'marcado': categoria.pk in selecionadas_pks}
        for categoria in form.fields['especialidades'].queryset
    ]

    return render(request, 'accounts/escolher_especialidade.html', {'form': form, 'cartoes': cartoes})


@login_required
def profile_edit(request):
    """U2 - Editar perfil / P2 - Editar dados profissionais."""
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            if request.FILES.get('foto'):
                profile.foto = request.FILES['foto']
            profile.save()
            form.save_m2m()
            messages.success(request, 'Dados atualizados com sucesso.')
            return redirect('home')
    else:
        form = ProfileEditForm(instance=profile)
    return render(request, 'accounts/profile_edit.html', {'form': form, 'profile': profile})


def consultar_cep_view(request):
    """
    Endpoint AJAX (GET ?cep=00000000) usado pelo JS dos formulários de
    cadastro/edição para autopreencher o endereço a partir do CEP,
    consultando a ViaCEP. A latitude/longitude
    (quando disponíveis) são calculadas e salvas de fato no `clean_cep`
    dos formulários — este endpoint serve apenas para dar feedback
    visual imediato ao usuário enquanto digita.
    """
    cep = request.GET.get('cep', '')
    try:
        dados = consultar_cep(cep)
    except CepInvalidoError as exc:
        return JsonResponse({'erro': str(exc)}, status=400)
    return JsonResponse(dados)
