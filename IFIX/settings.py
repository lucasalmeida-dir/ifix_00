"""
Configurações do projeto IFIX.

Estrutura baseada no diagrama:
- Autenticação (login, logout, recuperação de senha)
- Área do Usuário (cadastro, editar perfil, opções de serviços)
- Área do Profissional (cadastro, editar dados, opções de serviços/categorias)
"""
import os
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-troque-esta-chave-em-produzir-para-um-valor-seguro'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sitemaps',

    # Apps do projeto
    'accounts',
    'services',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.EspecialidadeObrigatoriaMiddleware',
    'accounts.middleware.TermosAceiteMiddleware',
]

ROOT_URLCONF = 'IFIX.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'services.context_processors.notificacoes_mensagens',
                'accounts.context_processors.google_login',
            ],
        },
    },
]

WSGI_APPLICATION = 'IFIX.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Autenticação ---
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

# E-mail: em modo de desenvolvimento, os e-mails (ex: recuperação de senha)
# são exibidos no console em vez de enviados de verdade.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'naoresponda@ifix.local'


# ---------------------------------------------------------------------------
# Regras de cancelamento / reagendamento (ver services/regras.py)
# ---------------------------------------------------------------------------
IFIX_CANCELAMENTO_ANTECEDENCIA_HORAS = 24
IFIX_REAGENDAMENTO_ANTECEDENCIA_HORAS = 12
IFIX_REAGENDAMENTO_MAX = 2

# ---------------------------------------------------------------------------
# Pagamento por Pix com retenção (ver services/pagamentos/)
#
# Enquanto o IFIX não tiver CNPJ e conta em um provedor (Asaas / Mercado
# Pago), o Pix fica DESLIGADO: nenhuma tela de pagamento aparece e o fluxo
# de orçamento segue como sempre. Para ligar depois:
#   1) IFIX_PIX_HABILITADO=1
#   2) IFIX_PIX_PROVEDOR=asaas   (ou mercadopago)
#   3) preencher as chaves do provedor abaixo (variáveis de ambiente)
#   4) implementar os TODO em services/pagamentos/asaas.py (ou mercadopago.py)
# Com IFIX_PIX_PROVEDOR=simulado (padrão) dá para testar todo o fluxo em
# modo DEBUG, com um botão de "simular pagamento".
# ---------------------------------------------------------------------------
PIX_HABILITADO = os.environ.get('IFIX_PIX_HABILITADO', '0') == '1'
PIX_PROVEDOR = os.environ.get('IFIX_PIX_PROVEDOR', 'simulado')
PIX_EXPIRACAO_MINUTOS = int(os.environ.get('IFIX_PIX_EXPIRACAO_MINUTOS', '30'))
IFIX_COMISSAO_PERCENTUAL = Decimal(os.environ.get('IFIX_COMISSAO_PERCENTUAL', '10'))

ASAAS_API_KEY = os.environ.get('ASAAS_API_KEY', '')
ASAAS_BASE_URL = os.environ.get('ASAAS_BASE_URL', 'https://sandbox.asaas.com/api/v3')
ASAAS_WEBHOOK_TOKEN = os.environ.get('ASAAS_WEBHOOK_TOKEN', '')

MERCADOPAGO_ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '')
MERCADOPAGO_WEBHOOK_SECRET = os.environ.get('MERCADOPAGO_WEBHOOK_SECRET', '')

# ---------------------------------------------------------------------------
# Login rápido com Google (Sign In With Google)
#
# Fica DESLIGADO (o botão continua "Em breve") até você criar um Client ID:
#   1) console.cloud.google.com -> criar projeto -> "APIs e serviços" ->
#      "Credenciais" -> "Criar credenciais" -> "ID do cliente OAuth" ->
#      tipo "Aplicativo da Web".
#   2) Em "Origens JavaScript autorizadas", adicione o domínio do site
#      (ex.: https://ifix.com.br e, para testar local, http://localhost:8000).
#   3) Defina a variável de ambiente GOOGLE_OAUTH_CLIENT_ID com o Client ID
#      gerado (algo como "123...apps.googleusercontent.com").
# Não precisa de client secret nem de biblioteca nova: o token que o Google
# devolve é conferido chamando a própria API do Google (ver
# accounts/services.py -> verificar_id_token_google).
#
# O WhatsApp não oferece um "Entrar com WhatsApp" equivalente ao do Google
# (não existe OAuth de identidade pelo WhatsApp) - por isso esse botão
# continua marcado "Em breve" e não foi implementado.
# ---------------------------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '')
