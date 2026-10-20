"""Paramètres pour pytest — SQLite en mémoire, pas de Redis, clés de test."""
from .base import *  # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Canal en mémoire (déjà le cas en base, mais explicite ici)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# Pas de throttle en tests — on vide les classes ET on garde des rates pour
# les vues qui déclarent throttle_classes explicitement (ex. FaceVerifyView)
REST_FRAMEWORK = {
    **globals().get('REST_FRAMEWORK', {}),
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {
        'user': '1000/day',
        'anon': '1000/day',
    },
}

SECRET_KEY = 'test-secret-key-not-for-production'

# Clé HMAC fallback si .env absent (CI sans secrets)
import os as _os
if not _os.environ.get('HMAC_SECRET_KEY'):
    HMAC_SECRET_KEY = 'test-hmac-key-not-for-production'
