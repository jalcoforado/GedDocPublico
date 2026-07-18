"""
Django settings for the Sistema de Gestão e Autorização de Pagamentos Municipais.
"""

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-)272p6=0khkfjlowl2*7065duveor*j2#xm044-b$gops8ez-d',
)

# Used to derive the Fernet key for encrypting sensitive fields at rest (RF66).
# In production, set FIELD_ENCRYPTION_KEY to a stable, secret value — if it
# changes, previously encrypted data (dados bancários) becomes unreadable.
FIELD_ENCRYPTION_KEY = config('FIELD_ENCRYPTION_KEY', default=SECRET_KEY)

DEBUG = config('DEBUG', default=True, cast=bool)

# Em DEBUG (dev local/preview), aceita qualquer host — o preview tool pode
# proxiar a porta atribuída dinamicamente por um hostname não previsível.
# Em produção (DEBUG=False), ALLOWED_HOSTS deve ser definido via variável
# de ambiente com os hosts reais.
ALLOWED_HOSTS = ['*'] if DEBUG else config('ALLOWED_HOSTS', default='', cast=Csv())


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    'rest_framework',

    'apps.core',
    'apps.accounts',
    'apps.cadastros',
    'apps.pagamentos',
    'apps.financeiro',
    'apps.conciliacao',
    'apps.relatorios',
    'apps.transparencia',
    'apps.auditoria',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.CurrentUserMiddleware',
    'apps.accounts.middleware.ForcePasswordChangeMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
                'apps.core.context_processors.perfil_usuario',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# Defaults to SQLite for zero-config local runs. Set DATABASE_URL to switch
# to PostgreSQL in production (recommended for MCASP/PCASP-scale deployments).
DATABASE_URL = config('DATABASE_URL', default='')

if DATABASE_URL:
    import dj_database_url
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'accounts.Usuario'

AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.LockoutEmailBackend',
]

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
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:home'
LOGOUT_REDIRECT_URL = 'accounts:login'

# RF65 — bloqueio temporário após tentativas malsucedidas de login.
LOGIN_ATTEMPT_LIMIT = config('LOGIN_ATTEMPT_LIMIT', default=5, cast=int)
LOGIN_LOCKOUT_MINUTES = config('LOGIN_LOCKOUT_MINUTES', default=15, cast=int)

# RF19 — notificações por e-mail. Backend console por padrão (sem SMTP real
# configurado neste ambiente); trocar por SMTP em produção via variáveis abaixo.
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=25, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=False, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='sistema-pagamentos@municipio.gov.br')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# RF37 — limite mínimo padrão de saldo (usado quando a conta não define o próprio limite).
SALDO_MINIMO_ALERTA_PADRAO = config('SALDO_MINIMO_ALERTA_PADRAO', default=0, cast=float)
