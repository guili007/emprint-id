"""
Permissions Module 05 — Eyeshield Audit.

Matrice d'accès :
  ROLE_ADMIN           → accès complet (lecture + écriture + génération rapports)
  ROLE_WATCHLIST_ADMIN → accès complet (supervision opérationnelle)
  Tous les autres      → 403

Le trail d'audit est sensible par nature : seuls les administrateurs
peuvent lire les actions de leurs collègues.
"""
from rest_framework.permissions import BasePermission

# Rôles avec accès en lecture au Module Audit
_AUDIT_READ_ROLES = {
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}

# Rôles avec accès en écriture (changer statut flag, générer rapport)
_AUDIT_WRITE_ROLES = {
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}


def _role(user) -> str:
    return getattr(user, 'role', '')


class IsAuditReader(BasePermission):
    """Administrateurs : lecture des événements, flags et rapports d'audit."""
    message = "Accès réservé aux administrateurs système (ROLE_ADMIN / WATCHLIST_ADMIN)."

    def has_permission(self, request, view):
        return _role(request.user) in _AUDIT_READ_ROLES


class IsAuditAdmin(BasePermission):
    """Administrateurs : génération de rapports et mise à jour des flags."""
    message = "Accès réservé aux administrateurs système (ROLE_ADMIN / WATCHLIST_ADMIN)."

    def has_permission(self, request, view):
        return _role(request.user) in _AUDIT_WRITE_ROLES
