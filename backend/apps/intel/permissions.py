"""
Permissions Module 04 — Eyeshield Intel.

Matrice accès :
  ROLE_INTEL           → lecture + écriture (analyste renseignement)
  ROLE_POLICE          → lecture seule (alertes + réseau + menaces)
  ROLE_BORDER          → lecture seule (menaces géographiques + alertes)
  ROLE_ADMIN           → accès total
  ROLE_WATCHLIST_ADMIN → accès total
  Tous les autres      → 403
"""
from rest_framework.permissions import BasePermission

# Rôles avec accès en lecture au Module Intel
_INTEL_READ_ROLES = {
    'ROLE_INTEL',
    'ROLE_POLICE',
    'ROLE_BORDER',
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}

# Rôles avec accès en écriture (créer alertes, ajouter liens, déclarer zones)
_INTEL_WRITE_ROLES = {
    'ROLE_INTEL',
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}


def _role(user) -> str:
    return getattr(user, 'role', '')


class IsIntelReader(BasePermission):
    """Agents sécurité accrédités : lecture des alertes, réseau, menaces."""
    message = "Accès réservé aux agents de renseignement accrédités."

    def has_permission(self, request, view):
        return _role(request.user) in _INTEL_READ_ROLES


class IsIntelAnalyst(BasePermission):
    """Analystes Intel : création et mise à jour d'alertes, liens, zones."""
    message = "Accès réservé aux analystes Intel (ROLE_INTEL ou ADMIN)."

    def has_permission(self, request, view):
        return _role(request.user) in _INTEL_WRITE_ROLES
