from rest_framework.permissions import BasePermission


FIELD_ROLES = {'ROLE_POLICE', 'ROLE_BANK', 'ROLE_BORDER', 'ROLE_HEALTH'}
ADMIN_ROLES = {'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}


def get_user_role(user) -> str:
    return getattr(user, 'role', '')


class IsFieldAgent(BasePermission):
    """Police, banque, frontière, santé — peuvent vérifier des identités."""
    message = "Accès réservé aux agents terrain."

    def has_permission(self, request, view):
        return get_user_role(request.user) in FIELD_ROLES | ADMIN_ROLES


class IsWatchlistAdmin(BasePermission):
    """Seul ce rôle peut écrire sur la watchlist."""
    message = "Accès réservé aux administrateurs watchlist."

    def has_permission(self, request, view):
        return get_user_role(request.user) == 'ROLE_WATCHLIST_ADMIN'
