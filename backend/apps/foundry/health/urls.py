"""URLs Foundry Health — sous-ensemble /api/v3/foundry/health/."""
from django.urls import path

from .views import (
    HealthPatientListView,
    HealthPatientDetailView,
    HealthVisitView,
    HealthVaccinationView,
    EpidemioAlertView,
    HealthStatsView,
)

urlpatterns = [
    # Dossiers patients
    path('patients/', HealthPatientListView.as_view(), name='health-patient-list'),
    path('patients/<str:national_id>/', HealthPatientDetailView.as_view(), name='health-patient-detail'),

    # Actes médicaux (append-only)
    path('visits/', HealthVisitView.as_view(), name='health-visit-create'),
    path('vaccinations/', HealthVaccinationView.as_view(), name='health-vaccination-create'),

    # Dashboard
    path('epidemio/', EpidemioAlertView.as_view(), name='health-epidemio'),
    path('stats/', HealthStatsView.as_view(), name='health-stats'),
]
