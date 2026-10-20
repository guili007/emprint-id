"""URLs Module 03 — Eyeshield Foundry."""
from django.urls import path

from .views import KYCView, FraudAlertListView

urlpatterns = [
    # Banking
    path('banking/kyc/', KYCView.as_view(), name='foundry-banking-kyc'),
    path('banking/fraud-alerts/', FraudAlertListView.as_view(), name='foundry-banking-fraud-alerts'),
]
