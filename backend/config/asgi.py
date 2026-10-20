import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

# get_asgi_application() déclenche django.setup() — DOIT être appelé en premier
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

# Imports des apps Django APRÈS django.setup()
from channels.routing import ProtocolTypeRouter, URLRouter
from apps.biometric.routing import websocket_urlpatterns
from config.ws_auth import JWTAuthMiddleware

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})
