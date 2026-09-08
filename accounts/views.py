from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from .forms import UserRegisterForm, ProfessionalRegisterForm, ProfileEditForm
from .models import Profile
from .services import CepInvalidoError, consultar_cep


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
            messages.success(request, 'Cadastro profissional realizado com sucesso!')
            return redirect('home')
    else:
        form = ProfessionalRegisterForm()
    return render(request, 'accounts/register_professional.html', {'form': form})


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
