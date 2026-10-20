"""Permissions Foundry Health."""
from rest_framework.permissions import BasePermission

# Rôles autorisés à accéder au dossier patient et enregistrer des actes
_HEALTH_ROLES = {'ROLE_HEALTH', 'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}

# Rôles autorisés aux données agrégées (épidémio, statistiques)
_HEALTH_ADMIN_ROLES = {'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}


class IsHealthWorker(BasePermission):
    """
    ROLE_HEALTH (et admins) peuvent lire les dossiers patients,
    enregistrer des visites et des vaccinations.
    """

    def has_permission(self, request, view):
        return getattr(request.user, 'role', '') in _HEALTH_ROLES


class IsHealthAdmin(BasePermission):
    """
    Seul ROLE_ADMIN / ROLE_WATCHLIST_ADMIN accède au dashboard épidémio
    et aux statistiques agrégées.
    """

    def has_permission(self, request, view):
        return getattr(request.user, 'role', '') in _HEALTH_ADMIN_ROLES
