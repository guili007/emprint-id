"""
Logique de détection de fraude inter-bancaire — Eyeshield Foundry Banking.
"""
from .models import FraudAlert

FRAUD_WINDOW_MINUTES = 60


def _severity_for_count(tenant_count: int) -> str:
    """
    Calcule la sévérité d'une alerte fraude selon le nombre de tenants impliqués.

    Retourne une valeur de FraudAlert.Severity :
      - FraudAlert.Severity.HIGH   si ≥ 5 tenants
      - FraudAlert.Severity.MEDIUM si 3 ou 4 tenants
      - FraudAlert.Severity.LOW    si 2 tenants

    """
    if tenant_count >= 5:
        return FraudAlert.Severity.HIGH
    if tenant_count >= 3:
        return FraudAlert.Severity.MEDIUM
    return FraudAlert.Severity.LOW
