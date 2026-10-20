"""
Permissions Foundry Edu.

Hiérarchie :
  ROLE_EDU        → agent scolaire (lecture des dossiers élèves)
  ROLE_ADMIN      → accès complet (stats + sync status)
  ROLE_WATCHLIST_ADMIN → idem ADMIN

Les autres rôles (BANK, HEALTH, GOV) n'ont aucun accès — isolation des secteurs.
"""
from rest_framework.permissions import BasePermission, IsAuthenticated

# Rôles autorisés à lire les données scolaires
_EDU_ROLES = {'ROLE_EDU', 'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}

# Rôles autorisés à voir les statistiques et l'état de synchronisation
_EDU_ADMIN_ROLES = {'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}


class IsEduReader(IsAuthenticated):
    """Lecture des dossiers scolaires (élèves, bulletins)."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        role = getattr(request.auth, 'payload', {}).get('role', '') if request.auth else ''
        return role in _EDU_ROLES


class IsEduAdmin(IsAuthenticated):
    """Statistiques agrégées et état de synchronisation EduFirst."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        role = getattr(request.auth, 'payload', {}).get('role', '') if request.auth else ''
        return role in _EDU_ADMIN_ROLES
