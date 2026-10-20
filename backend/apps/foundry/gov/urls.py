"""URLs Foundry Gov — sous-ensemble /api/v3/foundry/gov/."""
from django.urls import path

from .views import (
    GovEmployeeListView,
    GovEmployeeDetailView,
    GovStatsView,
    GovBudgetView,
    GovContractView,
)

urlpatterns = [
    # Liste des fonctionnaires (filtre ?statut=, ?administration=, ?q=)
    path('employees/', GovEmployeeListView.as_view(), name='gov-employee-list'),

    # Détail d'un fonctionnaire + ses événements de carrière
    path('employees/<uuid:siga_uuid>/', GovEmployeeDetailView.as_view(), name='gov-employee-detail'),

    # Statistiques agrégées (effectifs, top ministères)
    path('stats/', GovStatsView.as_view(), name='gov-stats'),

    # Budget public (mock v1, données réelles à intégrer)
    path('budget/', GovBudgetView.as_view(), name='gov-budget'),

    # Marchés publics (mock v1)
    path('contracts/', GovContractView.as_view(), name='gov-contracts'),
]
