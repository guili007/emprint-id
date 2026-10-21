"""URLs Module 09 — Eyeshield Health (v9/health/)."""
from django.urls import path

from .views import (
    EpidemioAlertListCreateView,
    HealthPatientDetailView,
    HealthPatientListCreateView,
    HealthPrescriptionCreateView,
    HealthStatsView,
    HealthVaccinationCreateView,
    HealthVisitCreateView,
)

urlpatterns = [
    path('patients/',                      HealthPatientListCreateView.as_view(),  name='health-patient-list'),
    path('patients/<str:national_id>/',    HealthPatientDetailView.as_view(),      name='health-patient-detail'),
    path('visits/',                        HealthVisitCreateView.as_view(),        name='health-visit-create'),
    path('vaccinations/',                  HealthVaccinationCreateView.as_view(),  name='health-vaccination-create'),
    path('prescriptions/',                 HealthPrescriptionCreateView.as_view(), name='health-prescription-create'),
    path('epidemio/',                      EpidemioAlertListCreateView.as_view(),  name='health-epidemio-list'),
    path('stats/',                         HealthStatsView.as_view(),              name='health-stats'),
]
