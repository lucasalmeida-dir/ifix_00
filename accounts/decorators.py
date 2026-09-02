from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def professional_required(view_func):
    """Permite acesso apenas a contas do tipo Profissional (Área do Profissional)."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.is_profissional:
            messages.error(request, 'Esta área é exclusiva para profissionais cadastrados.')
            return redirect('home')
        return view_func(request, *args, **kwargs)

    return _wrapped


def user_required(view_func):
    """Permite acesso apenas a contas do tipo Usuário (Área do Usuário)."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.is_usuario:
            messages.error(request, 'Esta área é exclusiva para usuários cadastrados.')
            return redirect('home')
        return view_func(request, *args, **kwargs)

    return _wrapped
