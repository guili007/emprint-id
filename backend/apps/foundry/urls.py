"""URLs Module 03 — Eyeshield Foundry."""
from django.urls import path, include

from .views import KYCView, FraudAlertListView

urlpatterns = [
    # Banking
    path('banking/kyc/', KYCView.as_view(), name='foundry-banking-kyc'),
    path('banking/fraud-alerts/', FraudAlertListView.as_view(), name='foundry-banking-fraud-alerts'),

    # Gov — dashboard opérationnel Ministères
    path('gov/', include('apps.foundry.gov.urls')),

    # Health — dossier patient unifié + épidémiologie
    path('health/', include('apps.foundry.health.urls')),
]
