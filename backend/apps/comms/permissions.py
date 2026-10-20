"""
Permissions Module 06 — Eyeshield Comms.

Matrice d'accès :
  ROLE_INTEL           → lecture + écriture (analyste renseignement)
  ROLE_POLICE          → lecture seule (enquêtes judiciaires)
  ROLE_BORDER          → lecture seule (trafic transfrontalier)
  ROLE_ADMIN           → accès total
  ROLE_WATCHLIST_ADMIN → accès total
  Tous les autres      → 403
"""
from rest_framework.permissions import BasePermission

_COMMS_READ_ROLES = {
    'ROLE_INTEL',
    'ROLE_POLICE',
    'ROLE_BORDER',
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}

_COMMS_WRITE_ROLES = {
    'ROLE_INTEL',
    'ROLE_ADMIN',
    'ROLE_WATCHLIST_ADMIN',
}


def _role(user) -> str:
    return getattr(user, 'role', '')


class IsCommsReader(BasePermission):
    """Agents accrédités : lecture des SIMs, CDR et alertes télécom."""
    message = "Accès réservé aux agents de renseignement ou forces de l'ordre accréditées."

    def has_permission(self, request, view):
        return _role(request.user) in _COMMS_READ_ROLES


class IsCommsAnalyst(BasePermission):
    """Analystes : enregistrement de SIMs, import CDR, création d'alertes."""
    message = "Accès réservé aux analystes télécom (ROLE_INTEL ou ADMIN)."

    def has_permission(self, request, view):
        return _role(request.user) in _COMMS_WRITE_ROLES
