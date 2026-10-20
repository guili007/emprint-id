"""
Permissions Module 08 — Eyeshield Justice.

Matrice d'accès :
  ROLE_POLICE          → lecture (vérification au terrain)
  ROLE_BORDER          → lecture (contrôle frontière)
  ROLE_INTEL           → lecture + écriture (analyse et création d'alertes)
  ROLE_ADMIN           → accès total
  ROLE_WATCHLIST_ADMIN → accès total
  Tous les autres      → 403

ROLE_BANK / ROLE_HEALTH / ROLE_EDU n'ont pas accès au casier judiciaire.
"""
from rest_framework.permissions import BasePermission

_JUSTICE_READ_ROLES = {
    'ROLE_POLICE',
    'ROLE_BORDER',
    'ROLE_INTEL',
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}

# ROLE_INTEL peut créer des alertes et des records ; ROLE_POLICE/BORDER lecture seule
_JUSTICE_WRITE_ROLES = {
    'ROLE_INTEL',
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}


def _role(user) -> str:
    return getattr(user, 'role', '')


class IsJusticeReader(BasePermission):
    """Accès lecture : casier, mandats, alertes."""
    message = "Accès réservé aux forces de l'ordre et analystes accrédités."

    def has_permission(self, request, view):
        return _role(request.user) in _JUSTICE_READ_ROLES


class IsJusticeWriter(BasePermission):
    """Accès écriture : création de records, mandats, alertes."""
    message = "Accès réservé aux analystes et administrateurs judiciaires."

    def has_permission(self, request, view):
        return _role(request.user) in _JUSTICE_WRITE_ROLES
