"""
Models Module 08 — Eyeshield Justice : casier judiciaire + mandats + alertes.

Trois piliers :
  CriminalRecord  — casier judiciaire APPEND-ONLY (condamnations, acquittements, pardons)
  ArrestWarrant   — mandat judiciaire (arrêt, perquisition, saisie)
  JusticeAlert    — alerte judiciaire APPEND-ONLY (recherché, fugitif, avis international)

Invariant clé :
  CriminalRecord et JusticeAlert : jamais DELETE ni UPDATE.
  Un casier se corrige en créant un PARDON ou ACQUITTAL, jamais en modifiant.
  ArrestWarrant.status peut évoluer ACTIVE→EXECUTED/CANCELLED/EXPIRED.
"""
from django.conf import settings
from django.db import models


class CriminalRecord(models.Model):
    """
    Entrée de casier judiciaire — APPEND-ONLY.

    Chaque acte judiciaire (condamnation, acquittement, grâce) est un record distinct.
    Un national_id peut avoir plusieurs records formant son historique pénal.
    """

    class RecordType(models.TextChoices):
        FELONY       = 'FELONY',       'Crime'
        MISDEMEANOR  = 'MISDEMEANOR',  'Délit'
        INFRACTION   = 'INFRACTION',   'Contravention'
        ACQUITTAL    = 'ACQUITTAL',    'Acquittement'
        PARDON       = 'PARDON',       'Grâce présidentielle'

    class SentenceType(models.TextChoices):
        PRISON            = 'PRISON',            'Emprisonnement'
        FINE              = 'FINE',              'Amende'
        COMMUNITY_SERVICE = 'COMMUNITY_SERVICE', "Travaux d'intérêt général"
        PROBATION         = 'PROBATION',         'Probation'
        ACQUITTED         = 'ACQUITTED',         'Acquitté'
        SUSPENDED         = 'SUSPENDED',         'Peine suspendue'

    national_id              = models.CharField(max_length=20, db_index=True)
    record_type              = models.CharField(max_length=12, choices=RecordType.choices, db_index=True)
    offense_code             = models.CharField(max_length=20, blank=True)
    offense_description      = models.TextField()
    judgment_date            = models.DateField()
    court_name               = models.CharField(max_length=200)
    sentence_type            = models.CharField(max_length=20, choices=SentenceType.choices)
    # Durée uniquement pour PRISON / PROBATION
    sentence_duration_months = models.PositiveSmallIntegerField(null=True, blank=True)
    # Montant uniquement pour FINE
    fine_amount_cdf          = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    # Date de libération prévue (calculée par la vue, jamais stockée par le client)
    release_date             = models.DateField(null=True, blank=True)
    created_by               = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='criminal_records_created'
    )
    created_at               = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-judgment_date']
        indexes  = [
            models.Index(fields=['national_id', 'record_type']),
            models.Index(fields=['national_id', 'judgment_date']),
        ]
        verbose_name        = 'casier judiciaire'
        verbose_name_plural = 'casiers judiciaires'

    def __str__(self):
        return f"[{self.record_type}] {self.national_id} — {self.court_name} {self.judgment_date}"


class ArrestWarrant(models.Model):
    """
    Mandat judiciaire émis par un tribunal.

    status est mutable : ACTIVE → EXECUTED / CANCELLED / EXPIRED.
    Jamais DELETE — les mandats exécutés ou annulés restent traçables.
    """

    class WarrantType(models.TextChoices):
        ARREST  = 'ARREST',  "Mandat d'arrêt"
        SEARCH  = 'SEARCH',  'Mandat de perquisition'
        SEIZURE = 'SEIZURE', 'Mandat de saisie'

    class WarrantStatus(models.TextChoices):
        ACTIVE    = 'ACTIVE',    'Actif'
        EXECUTED  = 'EXECUTED',  'Exécuté'
        CANCELLED = 'CANCELLED', 'Annulé'
        EXPIRED   = 'EXPIRED',   'Expiré'

    national_id         = models.CharField(max_length=20, db_index=True)
    warrant_type        = models.CharField(max_length=8,  choices=WarrantType.choices)
    issued_by           = models.CharField(max_length=200)
    issued_at           = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at          = models.DateTimeField(null=True, blank=True)
    status              = models.CharField(
        max_length=10, choices=WarrantStatus.choices, default=WarrantStatus.ACTIVE, db_index=True
    )
    offense_description = models.TextField()
    created_by          = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='warrants_issued'
    )
    executed_at         = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-issued_at']
        indexes  = [
            models.Index(fields=['national_id', 'status']),
        ]
        verbose_name        = 'mandat judiciaire'
        verbose_name_plural = 'mandats judiciaires'

    def __str__(self):
        return f"[{self.warrant_type}] {self.national_id} — {self.status}"


class JusticeAlert(models.Model):
    """
    Alerte judiciaire — APPEND-ONLY.

    Types : WANTED (recherché national), BAIL_JUMPER (fugitif sous caution),
    INTERNATIONAL_WANTED (Interpol/mandat international), COURT_ORDER (injonction tribunal).
    """

    class AlertType(models.TextChoices):
        WANTED               = 'WANTED',               'Recherché'
        BAIL_JUMPER          = 'BAIL_JUMPER',          'Fugitif sous caution'
        INTERNATIONAL_WANTED = 'INTERNATIONAL_WANTED', 'Recherché international'
        COURT_ORDER          = 'COURT_ORDER',          'Injonction judiciaire'

    class Severity(models.TextChoices):
        LOW      = 'LOW',      'Faible'
        MEDIUM   = 'MEDIUM',   'Moyen'
        HIGH     = 'HIGH',     'Élevé'
        CRITICAL = 'CRITICAL', 'Critique'

    class AlertStatus(models.TextChoices):
        ACTIVE   = 'ACTIVE',   'Active'
        RESOLVED = 'RESOLVED', 'Résolue'
        EXPIRED  = 'EXPIRED',  'Expirée'

    national_id  = models.CharField(max_length=20, db_index=True)
    alert_type   = models.CharField(max_length=22, choices=AlertType.choices, db_index=True)
    severity     = models.CharField(max_length=8,  choices=Severity.choices, default=Severity.MEDIUM)
    title        = models.CharField(max_length=200)
    description  = models.TextField()
    issued_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='justice_alerts_issued'
    )
    status       = models.CharField(
        max_length=10, choices=AlertStatus.choices, default=AlertStatus.ACTIVE, db_index=True
    )
    evidence     = models.JSONField(default=dict)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['national_id', 'status']),
            models.Index(fields=['alert_type', 'severity']),
        ]
        verbose_name        = 'alerte judiciaire'
        verbose_name_plural = 'alertes judiciaires'

    def __str__(self):
        return f"[{self.alert_type}] {self.national_id} — {self.severity}"
