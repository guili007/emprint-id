"""Permissions Foundry Gov."""
from rest_framework.permissions import BasePermission

# Rôles autorisés à lire le dashboard Gov
_GOV_ROLES = {'ROLE_GOV', 'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}

# Rôles autorisés aux données sensibles (stats, budget, marchés)
_GOV_ADMIN_ROLES = {'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}


class IsGovReader(BasePermission):
    """ROLE_GOV + admins peuvent voir la liste des fonctionnaires."""

    def has_permission(self, request, view):
        return getattr(request.user, 'role', '') in _GOV_ROLES


class IsGovAdmin(BasePermission):
    """Seul ROLE_ADMIN / ROLE_WATCHLIST_ADMIN accède aux stats, budget, marchés."""

    def has_permission(self, request, view):
        return getattr(request.user, 'role', '') in _GOV_ADMIN_ROLES
