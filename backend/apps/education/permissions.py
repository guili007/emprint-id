"""
Permissions Module 10 — Eyeshield Education.

Matrice d'accès :
  ROLE_EDU             → lecture + écriture (agents éducation)
  ROLE_ADMIN           → accès total
  ROLE_WATCHLIST_ADMIN → accès total
  Tous les autres      → 403
"""
from rest_framework.permissions import BasePermission

_EDU_ROLES = {
    'ROLE_EDU',
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}

_EDU_ADMIN_ROLES = {
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}


def _role(user) -> str:
    return getattr(user, 'role', '')


class IsEduWorker(BasePermission):
    """Accès standard : dossiers, résultats, diplômes, alertes."""
    message = "Accès réservé aux agents de l'éducation nationale accrédités."

    def has_permission(self, request, view):
        return _role(request.user) in _EDU_ROLES


class IsEduAdmin(BasePermission):
    """Accès étendu : stats agrégées, alertes DIPLOME_FAUX."""
    message = "Accès réservé aux administrateurs de l'éducation nationale."

    def has_permission(self, request, view):
        return _role(request.user) in _EDU_ADMIN_ROLES
