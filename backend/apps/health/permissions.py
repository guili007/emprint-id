"""
Permissions Module 09 — Eyeshield Health.

Matrice d'accès :
  ROLE_HEALTH          → lecture + écriture (agents de santé)
  ROLE_ADMIN           → accès total (dont épidémio)
  ROLE_WATCHLIST_ADMIN → accès total
  Tous les autres      → 403

Note : ROLE_POLICE / ROLE_INTEL n'ont pas accès aux données médicales
       (confidentialité médicale).
"""
from rest_framework.permissions import BasePermission

_HEALTH_ROLES = {
    'ROLE_HEALTH',
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}

_HEALTH_ADMIN_ROLES = {
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}


def _role(user) -> str:
    return getattr(user, 'role', '')


class IsHealthWorker(BasePermission):
    """Accès standard : dossiers, visites, vaccinations, prescriptions."""
    message = "Accès réservé aux agents de santé accrédités."

    def has_permission(self, request, view):
        return _role(request.user) in _HEALTH_ROLES


class IsHealthAdmin(BasePermission):
    """Accès étendu : alertes épidémio + stats agrégées."""
    message = "Accès réservé aux administrateurs santé."

    def has_permission(self, request, view):
        return _role(request.user) in _HEALTH_ADMIN_ROLES
