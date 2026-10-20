"""Permissions RBAC pour Eyeshield Foundry."""
from rest_framework.permissions import BasePermission

from .models import TenantAgent


def _get_tenant(request):
    """Retourne le TenantAgent actif pour l'utilisateur courant, ou None."""
    if not request.user or not request.user.is_authenticated:
        return None
    return (
        TenantAgent.objects
        .select_related('tenant')
        .filter(user=request.user, tenant__is_active=True)
        .first()
    )


class IsBankAgent(BasePermission):
    """L'utilisateur est un agent d'un tenant BANKING actif."""

    def has_permission(self, request, view):
        membership = _get_tenant(request)
        return bool(
            membership
            and membership.tenant.sector == 'BANKING'
            and getattr(request.user, 'role', '') == 'ROLE_BANK'
        )


class IsBankTenantAdmin(BasePermission):
    """L'utilisateur est admin d'un tenant BANKING (peut voir les alertes fraude)."""

    def has_permission(self, request, view):
        membership = _get_tenant(request)
        return bool(
            membership
            and membership.tenant.sector == 'BANKING'
            and membership.is_admin
            and getattr(request.user, 'role', '') == 'ROLE_BANK'
        )


class IsFoundryAdmin(BasePermission):
    """Accès réservé à ROLE_ADMIN et ROLE_WATCHLIST_ADMIN (supervision globale)."""

    _ROLES = {'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}

    def has_permission(self, request, view):
        return getattr(request.user, 'role', '') in self._ROLES
