from django.conf import settings


def google_login(request):
    """Deixa o Client ID do Google disponível em qualquer template, para
    montar (ou não) o botão real de "Entrar com Google" - ver
    GOOGLE_OAUTH_CLIENT_ID em IFIX/settings.py."""
    client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
    return {
        'google_client_id': client_id,
        'google_login_habilitado': bool(client_id),
    }
