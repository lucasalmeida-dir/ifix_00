from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import UserRegisterForm, ProfessionalRegisterForm, ProfileEditForm
from .models import Profile


def register_user(request):
    """U1 - Cadastro de usuário."""
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
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
        form = ProfessionalRegisterForm(request.POST)
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
        form = ProfileEditForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Dados atualizados com sucesso.')
            return redirect('home')
    else:
        form = ProfileEditForm(instance=profile)
    return render(request, 'accounts/profile_edit.html', {'form': form, 'profile': profile})
