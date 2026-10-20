"""
Models Module 07 — Eyeshield Field : agents terrain + synchronisation différée.

Quatre piliers :
  FieldAgent   — profil d'agent terrain (appareil + zone d'opération)
  FieldMission — mission assignée à un agent (PENDING → IN_PROGRESS → COMPLETED)
  FieldRecord  — enregistrement terrain APPEND-ONLY (créé hors-ligne, syncé plus tard)
  SyncBatch    — lot de synchronisation (un push depuis un appareil = un batch)

Invariant clé :
  FieldRecord.offline_at  = horodatage de création sur l'appareil (sans réseau)
  FieldRecord.synced_at   = horodatage d'arrivée au serveur (auto_now_add)
  L'écart mesure la durée hors-ligne — jamais supérieur à 72h sans alerte.
"""
from django.conf import settings
from django.db import models


class FieldAgent(models.Model):
    """
    Profil d'agent terrain — lié à un compte User Django.
    Un User peut avoir un seul FieldAgent actif à la fois.
    """

    class AgentStatus(models.TextChoices):
        ACTIVE    = 'ACTIVE',    'Actif'
        INACTIVE  = 'INACTIVE',  'Inactif'
        SUSPENDED = 'SUSPENDED', 'Suspendu'

    agent        = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='field_profile'
    )
    # Identifiant unique de l'appareil mobile (Android ID ou UUID généré à l'install)
    device_id    = models.CharField(max_length=64, blank=True, db_index=True)
    zone_province = models.CharField(max_length=100, blank=True)
    zone_territoire = models.CharField(max_length=100, blank=True)
    status       = models.CharField(
        max_length=10, choices=AgentStatus.choices, default=AgentStatus.ACTIVE
    )
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'agent terrain'
        verbose_name_plural = 'agents terrain'

    def __str__(self):
        return f"{self.agent.username} ({self.zone_province or 'zone inconnue'})"


class FieldMission(models.Model):
    """Mission assignée à un agent terrain."""

    class MissionType(models.TextChoices):
        VERIFICATION  = 'VERIFICATION',  'Vérification identité'
        CENSUS        = 'CENSUS',        'Recensement'
        PATROL        = 'PATROL',        'Patrouille'
        INVESTIGATION = 'INVESTIGATION', 'Enquête terrain'
        CONTROL       = 'CONTROL',       'Contrôle frontière'

    class MissionStatus(models.TextChoices):
        PENDING     = 'PENDING',     'En attente'
        IN_PROGRESS = 'IN_PROGRESS', 'En cours'
        COMPLETED   = 'COMPLETED',   'Terminée'
        CANCELLED   = 'CANCELLED',   'Annulée'

    agent        = models.ForeignKey(
        FieldAgent, on_delete=models.CASCADE, related_name='missions'
    )
    title        = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    mission_type = models.CharField(max_length=15, choices=MissionType.choices)
    province     = models.CharField(max_length=100, blank=True)
    territoire   = models.CharField(max_length=100, blank=True)
    status       = models.CharField(
        max_length=12, choices=MissionStatus.choices, default=MissionStatus.PENDING
    )
    assigned_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_field_missions'
    )
    assigned_at  = models.DateTimeField(auto_now_add=True)
    started_at   = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    due_date     = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-assigned_at']
        indexes  = [
            models.Index(fields=['agent', 'status']),
            models.Index(fields=['status', 'due_date']),
        ]
        verbose_name        = 'mission terrain'
        verbose_name_plural = 'missions terrain'

    def __str__(self):
        return f"[{self.mission_type}] {self.title} — {self.status}"


class FieldRecord(models.Model):
    """
    Enregistrement terrain créé hors-ligne et synchronisé plus tard.

    APPEND-ONLY : jamais modifier ni supprimer — chaque observation terrain
    est une preuve datée. Pour corriger, créer un nouvel enregistrement.
    """

    class RecordType(models.TextChoices):
        VERIFICATION = 'VERIFICATION', 'Vérification identité'
        OBSERVATION  = 'OBSERVATION',  'Observation terrain'
        ARREST       = 'ARREST',       'Interpellation'
        SEIZURE      = 'SEIZURE',      'Saisie'
        INCIDENT     = 'INCIDENT',     'Incident sécuritaire'
        CHECKPOINT   = 'CHECKPOINT',   'Passage checkpoint'

    mission     = models.ForeignKey(
        FieldMission, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='records'
    )
    field_agent = models.ForeignKey(
        FieldAgent, on_delete=models.CASCADE, related_name='records'
    )
    record_type  = models.CharField(max_length=15, choices=RecordType.choices, db_index=True)
    national_id  = models.CharField(max_length=20, blank=True, db_index=True)
    description  = models.TextField(blank=True)
    # Coordonnées GPS : {"lat": -4.32, "lon": 15.32} ou {} si indisponible
    coordinates  = models.JSONField(default=dict)
    province     = models.CharField(max_length=100, blank=True)
    territoire   = models.CharField(max_length=100, blank=True)
    # Horodatage de création sur l'appareil (avant synchronisation)
    offline_at   = models.DateTimeField(db_index=True)
    # Horodatage d'arrivée au serveur (auto)
    synced_at    = models.DateTimeField(auto_now_add=True, db_index=True)
    evidence     = models.JSONField(default=dict)

    class Meta:
        ordering = ['-offline_at']
        indexes  = [
            models.Index(fields=['field_agent', 'offline_at']),
            models.Index(fields=['record_type', 'synced_at']),
        ]
        verbose_name        = 'enregistrement terrain'
        verbose_name_plural = 'enregistrements terrain'

    def __str__(self):
        return (
            f"[{self.record_type}] {self.field_agent} "
            f"offline={self.offline_at:%Y-%m-%d %H:%M} "
            f"sync={self.synced_at:%Y-%m-%d %H:%M}"
        )


class SyncBatch(models.Model):
    """
    Lot de synchronisation — un push depuis un appareil = un SyncBatch.

    Permet de tracer les synchronisations : quand, depuis quel appareil,
    combien de records, succès/échec partiel.
    """

    class BatchStatus(models.TextChoices):
        PENDING  = 'PENDING',  'En cours de traitement'
        COMPLETE = 'COMPLETE', 'Complet'
        PARTIAL  = 'PARTIAL',  'Partiel (certains records rejetés)'
        FAILED   = 'FAILED',   'Échec'

    field_agent     = models.ForeignKey(
        FieldAgent, on_delete=models.CASCADE, related_name='sync_batches'
    )
    device_id       = models.CharField(max_length=64, blank=True)
    records_count   = models.PositiveIntegerField(default=0)
    accepted_count  = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    synced_at       = models.DateTimeField(auto_now_add=True, db_index=True)
    status          = models.CharField(
        max_length=10, choices=BatchStatus.choices, default=BatchStatus.PENDING
    )
    error_log       = models.JSONField(default=list)

    class Meta:
        ordering = ['-synced_at']
        verbose_name        = 'batch sync'
        verbose_name_plural = 'batchs sync'

    def __str__(self):
        return f"SyncBatch {self.field_agent} — {self.records_count} records ({self.status})"
