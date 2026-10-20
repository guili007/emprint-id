"""
JWT personnalisé EmPrint-iD — classes d'authentification uniquement.
NE PAS importer rest_framework.views ici (circular import avec DRF settings).
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        role = ''
        try:
            role = user.profile.role
        except Exception:
            pass
        token['role'] = role
        token['username'] = user.username
        return token


class RoleJWTAuthentication(JWTAuthentication):
    """Attache token['role'] sur request.user — sans DB lookup supplémentaire."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        user.role = validated_token.get('role', '')
        return user
