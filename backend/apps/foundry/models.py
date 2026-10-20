"""
Module 03 — Eyeshield Foundry.

Modèles :
  Sector        : BANKING | GOV | HEALTH | EDU
  SectorTenant  : organisation abonnée (Rawbank, Ministère Finance, etc.)
  FraudAlert    : alerte fraude inter-bancaire (même ID dans N banques simultanément)
"""
import uuid

from django.conf import settings
from django.db import models


class Sector(models.TextChoices):
    BANKING = 'BANKING', 'Eyeshield Banking'
    GOV     = 'GOV',     'Eyeshield Gov'
    HEALTH  = 'HEALTH',  'Eyeshield Health'
    EDU     = 'EDU',     'Eyeshield Edu'


class SectorTenant(models.Model):
    """
    Organisation abonnée à un secteur Foundry.

    Exemples : Rawbank (BANKING), Ministère des Finances (GOV),
               Hôpital Général de Kinshasa (HEALTH), EduFirst (EDU).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, unique=True)
    sector = models.CharField(max_length=10, choices=Sector.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    api_key_hash = models.CharField(
        max_length=64, unique=True, null=True, blank=True, default=None,
        help_text="SHA-256 de la clé API SaaS — jamais en clair."
    )

    class Meta:
        verbose_name = "tenant Foundry"
        ordering = ['sector', 'name']

    def __str__(self):
        return f"[{self.sector}] {self.name}"


class TenantAgent(models.Model):
    """
    Lie un compte User EmPrint-iD à un tenant Foundry.
    Un agent peut appartenir à plusieurs tenants (ex. admin groupe bancaire).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_memberships'
    )
    tenant = models.ForeignKey(SectorTenant, on_delete=models.CASCADE, related_name='agents')
    is_admin = models.BooleanField(
        default=False,
        help_text="Admin du tenant — peut voir les alertes fraude et les stats du secteur."
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'tenant')]
        verbose_name = "agent tenant"

    def __str__(self):
        return f"{self.user.username} → {self.tenant.name}"


class FraudAlert(models.Model):
    """
    Alerte fraude inter-bancaire.

    Déclenchée quand le même national_id est vérifié par ≥ N tenants
    distincts dans une fenêtre de temps configurable.
    """

    class Severity(models.TextChoices):
        HIGH   = 'HIGH',   'Critique — même ID dans 5+ banques'
        MEDIUM = 'MEDIUM', 'Élevée — même ID dans 3-4 banques'
        LOW    = 'LOW',    'Faible — même ID dans 2 banques'

    national_id = models.CharField(max_length=20, db_index=True)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    tenant_count = models.PositiveSmallIntegerField(
        help_text="Nombre de tenants distincts ayant vérifié cet ID dans la fenêtre."
    )
    tenant_names = models.JSONField(
        default=list,
        help_text="Liste des noms de tenants impliqués."
    )
    window_minutes = models.PositiveSmallIntegerField(default=60)
    detected_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='resolved_fraud_alerts'
    )

    class Meta:
        verbose_name = "alerte fraude"
        indexes = [
            models.Index(fields=['national_id', 'detected_at']),
            models.Index(fields=['is_resolved', 'detected_at']),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.national_id} × {self.tenant_count} banques"


class KYCRecord(models.Model):
    """
    Journal immuable des vérifications KYC par tenant bancaire.

    Utilisé pour la détection de fraude inter-bancaire :
    si le même national_id apparaît dans ≥ 2 tenants sur la fenêtre,
    un FraudAlert est créé automatiquement.
    """

    class KYCStatus(models.TextChoices):
        CONFORME     = 'CONFORME',     'Identité confirmée'
        NON_CONFORME = 'NON_CONFORME', 'Identité non confirmée'

    national_id = models.CharField(max_length=20, db_index=True)
    tenant = models.ForeignKey(
        SectorTenant, on_delete=models.CASCADE, related_name='kyc_records'
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='kyc_records'
    )
    status = models.CharField(max_length=15, choices=KYCStatus.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "enregistrement KYC"
        indexes = [
            models.Index(fields=['national_id', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
        ]

    def __str__(self):
        return f"KYC {self.status} — {self.national_id} @ {self.tenant.name}"
