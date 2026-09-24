"""Armazenamento PRIVADO para documentos de verificação.

Documento e foto de verificação de identidade são dados sensíveis (LGPD):
ficam numa pasta fora de /media/ (que é pública) e só saem pelo painel
administrativo, numa view que exige usuário da equipe (staff). Ver
accounts/views_seguranca.py -> arquivo_verificacao.
"""
from django.conf import settings
from django.core.files.storage import FileSystemStorage


def armazenamento_privado():
    return FileSystemStorage(location=settings.BASE_DIR / 'private_media')
