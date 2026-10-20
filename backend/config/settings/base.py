from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR.parent / '.env')

SECRET_KEY = os.environ['SECRET_KEY']
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'channels',
    # Apps
    'apps.citizens',
    'apps.biometric',
    'apps.data',
    'apps.foundry',
    'apps.intel',
    'apps.audit',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'emprint_db'),
        'USER': os.environ.get('DB_USER', 'emprint'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Kinshasa'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Foundry Gov : connexion SIGA-RDC ────────────────────────────────────────
# Ces variables sont lues par SIGAConnector (apps/foundry/gov/connector.py).
# En développement, elles peuvent rester vides — sync_siga échouera proprement.
# En production, les valoriser via les secrets de déploiement (ne PAS les committer).
SIGA_BASE_URL = os.environ.get('SIGA_BASE_URL', '')
SIGA_SERVICE_USER = os.environ.get('SIGA_SERVICE_USER', '')
SIGA_SERVICE_PASSWORD = os.environ.get('SIGA_SERVICE_PASSWORD', '')

# ── Foundry Edu : connexion EduFirst ─────────────────────────────────────────
# Lues par sync_edufirst (apps/foundry/management/commands/sync_edufirst.py).
# En production : EDUFIRST_BASE_URL=https://api.edufirst.pro
# Ne PAS committer les vraies valeurs.
EDUFIRST_BASE_URL         = os.environ.get('EDUFIRST_BASE_URL', 'https://api.edufirst.pro')
EDUFIRST_SERVICE_EMAIL    = os.environ.get('EDUFIRST_SERVICE_EMAIL', '')
EDUFIRST_SERVICE_PASSWORD = os.environ.get('EDUFIRST_SERVICE_PASSWORD', '')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'config.auth.RoleJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '10/min',       # max 10 req/min sur endpoints biométriques
        'anon': '5/min',
    },
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=int(os.environ.get('JWT_EXPIRY_HOURS', 8))),
    'ALGORITHM': 'HS256',
}

# DeepFace
DEEPFACE_HOME = os.environ.get('DEEPFACE_HOME', str(BASE_DIR / '.deepface'))
FACE_SIMILARITY_THRESHOLD = float(os.environ.get('FACE_SIMILARITY_THRESHOLD', 0.85))
LIVENESS_THRESHOLD = float(os.environ.get('LIVENESS_THRESHOLD', 0.7))

# Cryptographie
HMAC_SECRET_KEY = os.environ.get('HMAC_SECRET_KEY', '')

def _resolve_key_path(env_val: str) -> str:
    """Résout un path relatif par rapport à la racine du projet (parent de backend/)."""
    if not env_val:
        return ''
    from pathlib import Path as _Path
    p = _Path(env_val)
    return str(p if p.is_absolute() else BASE_DIR.parent / p)

ECDSA_PRIVATE_KEY_PATH = _resolve_key_path(os.environ.get('ECDSA_PRIVATE_KEY_PATH', ''))
ECDSA_PUBLIC_KEY_PATH  = _resolve_key_path(os.environ.get('ECDSA_PUBLIC_KEY_PATH', ''))

# Redis / Channels
# Dev : bascule sur InMemoryChannelLayer si Redis n'est pas disponible
def _channel_layer_config():
    import socket
    redis_url = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    try:
        host, port_str = redis_url.replace('redis://', '').split('/')[0].split(':')
        s = socket.create_connection((host, int(port_str)), timeout=0.5)
        s.close()
        return {
            'default': {
                'BACKEND': 'channels_redis.core.RedisChannelLayer',
                'CONFIG': {'hosts': [redis_url]},
            }
        }
    except Exception:
        return {
            'default': {
                'BACKEND': 'channels.layers.InMemoryChannelLayer',
            }
        }

CHANNEL_LAYERS = _channel_layer_config()

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'https://verify.eyeshield.org',
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'emprint.biometric': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
