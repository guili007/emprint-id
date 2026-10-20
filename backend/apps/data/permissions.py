"""
Permissions Module 02 — Eyeshield Data.

Matrice "besoin d'en connaître" :
  ROLE_ADMIN / ROLE_WATCHLIST_ADMIN → accès total (État / Justice)
  ROLE_POLICE                       → citoyens + alertes CIVIL (Gouvernement)
  ROLE_BORDER                       → citoyens + alertes MILITAIRE (Armées)
  ROLE_HEALTH / ROLE_BANK           → citoyens uniquement, sans watchlist
"""
from rest_framework.permissions import BasePermission


DATA_ACCESS_ROLES = {
    'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN',
    'ROLE_POLICE', 'ROLE_BORDER', 'ROLE_HEALTH', 'ROLE_BANK',
}

ANALYTICS_ROLES = {'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}


def _role(user) -> str:
    return getattr(user, 'role', '')


class IsDataReader(BasePermission):
    """Tous les agents terrain + admins peuvent lire les données unifiées."""
    message = "Accès réservé aux agents accrédités Eyeshield."

    def has_permission(self, request, view):
        return _role(request.user) in DATA_ACCESS_ROLES


class IsAnalyticsAccess(BasePermission):
    """Seuls les admins voient les statistiques globales."""
    message = "Accès réservé aux administrateurs (État / Justice)."

    def has_permission(self, request, view):
        return _role(request.user) in ANALYTICS_ROLES
