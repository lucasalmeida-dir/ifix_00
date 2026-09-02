from django.shortcuts import render


def home(request):
    """Página inicial: mostra opções diferentes para visitante, usuário e profissional."""
    return render(request, 'home.html')
