"""
Models Module 05 — Eyeshield Audit : trail d'audit immuable + conformité.

Trois piliers :
  AuditEvent      — journal d'actions administratives (APPEND-ONLY)
  ComplianceFlag  — marqueur de non-conformité (statut updateable, jamais DELETE)
  AuditReport     — rapport de conformité généré (APPEND-ONLY)

Règles d'or :
  - AuditEvent   : jamais DELETE ni UPDATE — c'est la preuve légale
  - AuditReport  : jamais DELETE ni UPDATE — instantané signé d'une période
  - ComplianceFlag: statut peut changer (OPEN → REVIEWED / DISMISSED), jamais DELETE
"""
from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """
    Journal d'audit administratif — chaque action sensible laisse une trace.

    APPEND-ONLY : ne jamais modifier ni supprimer un enregistrement existant.
    Chaque ligne est une preuve horodatée de qui a fait quoi.
    """

    class EventType(models.TextChoices):
        LOGIN            = 'LOGIN',            'Connexion agent'
        LOGOUT           = 'LOGOUT',           'Déconnexion agent'
        DATA_ACCESS      = 'DATA_ACCESS',      'Accès à un dossier citoyen'
        WATCHLIST_ADD    = 'WATCHLIST_ADD',    'Ajout watchlist'
        WATCHLIST_REMOVE = 'WATCHLIST_REMOVE', 'Retrait watchlist'
        ROLE_CHANGE      = 'ROLE_CHANGE',      'Changement de rôle'
        CONFIG_CHANGE    = 'CONFIG_CHANGE',    'Modification configuration'
        EXPORT           = 'EXPORT',           'Export de données'
        ALERT_STATUS     = 'ALERT_STATUS',     'Changement statut alerte'
        MANUAL_OVERRIDE  = 'MANUAL_OVERRIDE',  'Intervention manuelle'

    event_type       = models.CharField(max_length=20, choices=EventType.choices, db_index=True)
    # Acteur — SET_NULL pour garder le log même si l'utilisateur est supprimé
    actor            = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='audit_events'
    )
    # Snapshot du rôle au moment de l'action — le rôle peut changer ensuite
    actor_role       = models.CharField(max_length=30, blank=True)
    target_national_id = models.CharField(max_length=20, blank=True, db_index=True)
    # Adresse IP de la requête entrante
    ip_address       = models.GenericIPAddressField(null=True, blank=True)
    # Contexte libre : identifiants concernés, ancienne/nouvelle valeur, etc.
    details          = models.JSONField(default=dict)
    created_at       = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['actor', 'created_at']),
        ]
        verbose_name        = 'événement audit'
        verbose_name_plural = 'événements audit'

    def __str__(self):
        return f"[{self.event_type}] {self.actor_role} — {self.created_at:%Y-%m-%d %H:%M}"


class ComplianceFlag(models.Model):
    """
    Marqueur de non-conformité levé automatiquement ou manuellement.

    Le statut peut progresser (OPEN → REVIEWED ou DISMISSED) mais
    l'enregistrement ne peut jamais être supprimé.
    """

    class FlagType(models.TextChoices):
        UNUSUAL_HOUR     = 'UNUSUAL_HOUR',     'Vérification hors-horaires (22h-5h)'
        HIGH_FREQUENCY   = 'HIGH_FREQUENCY',   'Fréquence anormale (>30/heure)'
        BULK_ACCESS      = 'BULK_ACCESS',      'Accès massif (>50 citoyens/jour)'
        CROSS_SECTOR     = 'CROSS_SECTOR',     'Accès multi-secteurs non justifié'
        UNAUTHORIZED_ATTEMPT = 'UNAUTHORIZED_ATTEMPT', "Tentative d'accès non autorisé"

    class Severity(models.TextChoices):
        LOW    = 'LOW',    'Faible'
        MEDIUM = 'MEDIUM', 'Modéré'
        HIGH   = 'HIGH',   'Élevé'

    class FlagStatus(models.TextChoices):
        OPEN      = 'OPEN',      'Ouvert'
        REVIEWED  = 'REVIEWED',  'Examiné'
        DISMISSED = 'DISMISSED', 'Classé sans suite'

    flag_type          = models.CharField(max_length=25, choices=FlagType.choices, db_index=True)
    severity           = models.CharField(max_length=10, choices=Severity.choices)
    actor              = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='compliance_flags_as_actor'
    )
    actor_role         = models.CharField(max_length=30, blank=True)
    target_national_id = models.CharField(max_length=20, blank=True, db_index=True)
    description        = models.TextField(blank=True)
    status             = models.CharField(
        max_length=12, choices=FlagStatus.choices, default=FlagStatus.OPEN, db_index=True
    )
    # Qui a examiné / classé ce flag
    reviewed_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='compliance_flags_reviewed'
    )
    reviewed_at        = models.DateTimeField(null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['flag_type', 'status']),
            models.Index(fields=['actor', 'created_at']),
        ]
        verbose_name        = 'flag conformité'
        verbose_name_plural = 'flags conformité'

    def __str__(self):
        return f"[{self.severity}] {self.flag_type} — {self.status}"


class AuditReport(models.Model):
    """
    Rapport de conformité généré pour une période donnée.

    APPEND-ONLY : chaque rapport est un instantané signé — jamais modifié.
    Un nouveau rapport pour la même période crée un nouvel enregistrement.
    """

    class ReportType(models.TextChoices):
        DAILY   = 'DAILY',   'Quotidien'
        WEEKLY  = 'WEEKLY',  'Hebdomadaire'
        MONTHLY = 'MONTHLY', 'Mensuel'
        CUSTOM  = 'CUSTOM',  'Personnalisé'

    class ReportStatus(models.TextChoices):
        PENDING  = 'PENDING',  'En cours de génération'
        COMPLETE = 'COMPLETE', 'Terminé'
        FAILED   = 'FAILED',   'Échec'

    report_type  = models.CharField(max_length=10, choices=ReportType.choices)
    period_start = models.DateField()
    period_end   = models.DateField()
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='generated_audit_reports'
    )
    generated_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status       = models.CharField(
        max_length=10, choices=ReportStatus.choices, default=ReportStatus.PENDING
    )
    # Données agrégées : verifications_total, flags_open, alerts_critical, etc.
    summary      = models.JSONField(default=dict)

    class Meta:
        ordering = ['-generated_at']
        indexes  = [
            models.Index(fields=['report_type', 'period_start']),
        ]
        verbose_name        = 'rapport audit'
        verbose_name_plural = 'rapports audit'

    def __str__(self):
        return f"[{self.report_type}] {self.period_start} → {self.period_end} ({self.status})"
