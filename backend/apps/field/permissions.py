"""
Permissions Module 07 — Eyeshield Field.

Matrice d'accès :
  ROLE_POLICE          → lecture + sync (agents terrain)
  ROLE_BORDER          → lecture + sync (contrôle frontière)
  ROLE_INTEL           → lecture seule (analyse des observations)
  ROLE_ADMIN           → accès total (gestion missions + agents)
  ROLE_WATCHLIST_ADMIN → accès total
  Tous les autres      → 403
"""
from rest_framework.permissions import BasePermission

_FIELD_READ_ROLES = {
    'ROLE_POLICE',
    'ROLE_BORDER',
    'ROLE_INTEL',
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}

# Rôles autorisés à synchroniser des records et créer des missions
_FIELD_WRITE_ROLES = {
    'ROLE_POLICE',
    'ROLE_BORDER',
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}


def _role(user) -> str:
    return getattr(user, 'role', '')


class IsFieldReader(BasePermission):
    """Accès lecture : enregistrements terrain, missions, stats."""
    message = "Accès réservé aux agents terrain ou analystes accrédités."

    def has_permission(self, request, view):
        return _role(request.user) in _FIELD_READ_ROLES


class IsFieldWriter(BasePermission):
    """Accès écriture : synchronisation, création de missions."""
    message = "Accès réservé aux agents terrain accrédités (ROLE_POLICE / BORDER / ADMIN)."

    def has_permission(self, request, view):
        return _role(request.user) in _FIELD_WRITE_ROLES
