"""
Middleware JWT pour Django Channels.
Lit le token depuis ?token=<JWT> dans la query string du WebSocket.
Attache user + role au scope.
"""
from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model

User = get_user_model()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        params = parse_qs(query_string)
        token_list = params.get('token', [])

        scope['user'] = AnonymousUser()
        scope['role'] = ''

        if token_list:
            try:
                token = AccessToken(token_list[0])
                user_id = token['user_id']
                user = await User.objects.aget(pk=user_id)
                user.role = token.get('role', '')
                scope['user'] = user
                scope['role'] = user.role
            except (InvalidToken, TokenError, User.DoesNotExist):
                pass

        return await super().__call__(scope, receive, send)
