"""
Models Module 06 — Eyeshield Comms : croisement télécom + liaisons SIM/IMEI.

Trois piliers :
  SimCard     — carte SIM enregistrée, liaison MSISDN ↔ IMEI ↔ national_id
  CallRecord  — enregistrement CDR (Call Detail Record) APPEND-ONLY
  CommsAlert  — alerte corrélation télécom APPEND-ONLY

Opérateurs RDC : MTN, VODACOM, AIRTEL, ORANGE, AFRICELL
MSISDN format  : +243XXXXXXXXX (9 chiffres après l'indicatif)
IMEI format    : 15 chiffres (TAC + SNR + check digit)
"""
from django.conf import settings
from django.db import models


class SimCard(models.Model):
    """
    Carte SIM enregistrée — point d'entrée du croisement télécom.

    Un citoyen peut avoir plusieurs SIMs (multi-SIM légal en RDC).
    Un IMEI peut être associé à plusieurs SIMs successives (changement de SIM).
    """

    class Operator(models.TextChoices):
        MTN       = 'MTN',       'MTN Congo'
        VODACOM   = 'VODACOM',   'Vodacom Congo'
        AIRTEL    = 'AIRTEL',    'Airtel Congo'
        ORANGE    = 'ORANGE',    'Orange Congo'
        AFRICELL  = 'AFRICELL',  'Africell Congo'
        UNKNOWN   = 'UNKNOWN',   'Opérateur inconnu'

    class SimStatus(models.TextChoices):
        ACTIVE      = 'ACTIVE',      'Active'
        SUSPENDED   = 'SUSPENDED',   'Suspendue'
        BLACKLISTED = 'BLACKLISTED', 'Liste noire'
        EXPIRED     = 'EXPIRED',     'Expirée'

    # MSISDN : numéro de téléphone international — clé métier principale
    msisdn          = models.CharField(max_length=20, unique=True, db_index=True)
    # IMEI du dernier appareil utilisé avec cette SIM
    imei            = models.CharField(max_length=20, blank=True, db_index=True)
    # Propriétaire enregistré — lié à l'ID national EmPrint-iD
    national_id     = models.CharField(max_length=20, blank=True, db_index=True)
    operator        = models.CharField(max_length=10, choices=Operator.choices, default=Operator.UNKNOWN)
    status          = models.CharField(max_length=12, choices=SimStatus.choices, default=SimStatus.ACTIVE)
    registered_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='registered_sims'
    )
    registered_at   = models.DateTimeField(auto_now_add=True)
    # Dernière fois que cette SIM a généré un CDR dans le système
    last_seen_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-registered_at']
        indexes  = [
            models.Index(fields=['national_id', 'status']),
            models.Index(fields=['imei']),
        ]
        verbose_name        = 'carte SIM'
        verbose_name_plural = 'cartes SIM'

    def __str__(self):
        return f"{self.msisdn} ({self.operator}) → {self.national_id or 'non identifié'}"


class CallRecord(models.Model):
    """
    Enregistrement CDR (Call Detail Record) — données de trafic télécom.

    APPEND-ONLY : les CDR sont importés depuis les opérateurs, jamais modifiés.
    Source de vérité pour la corrélation réseau et la détection de patterns.
    """

    class CallType(models.TextChoices):
        VOICE = 'VOICE', 'Appel vocal'
        SMS   = 'SMS',   'SMS'
        DATA  = 'DATA',  'Session data'

    caller_msisdn   = models.CharField(max_length=20, db_index=True)
    callee_msisdn   = models.CharField(max_length=20, db_index=True)
    call_type       = models.CharField(max_length=5, choices=CallType.choices)
    # Durée en secondes — 0 pour SMS et DATA
    duration_sec    = models.PositiveIntegerField(default=0)
    started_at      = models.DateTimeField(db_index=True)
    # Identifiant de l'antenne-relais (BTS) — pour la géolocalisation approximative
    cell_tower_id   = models.CharField(max_length=20, blank=True)
    province        = models.CharField(max_length=100, blank=True)
    # IMEI utilisé côté appelant au moment du CDR
    caller_imei     = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes  = [
            models.Index(fields=['caller_msisdn', 'started_at']),
            models.Index(fields=['callee_msisdn', 'started_at']),
            models.Index(fields=['started_at']),
        ]
        verbose_name        = 'enregistrement CDR'
        verbose_name_plural = 'enregistrements CDR'

    def __str__(self):
        return f"{self.caller_msisdn} → {self.callee_msisdn} [{self.call_type}] {self.started_at:%Y-%m-%d %H:%M}"


class CommsAlert(models.Model):
    """
    Alerte de corrélation télécom générée par analyse des CDR.

    APPEND-ONLY : une alerte créée ne peut être ni modifiée ni supprimée.
    Utiliser `status` pour marquer la résolution.
    """

    class AlertType(models.TextChoices):
        IMEI_SWAP         = 'IMEI_SWAP',         'Swap IMEI (SIM utilisée sur plusieurs appareils)'
        MULTI_SIM         = 'MULTI_SIM',          'Multi-SIM (même personne, plusieurs numéros)'
        FREQUENT_CONTACT  = 'FREQUENT_CONTACT',  'Contact fréquent suspect (>X appels/jour)'
        SIM_CLONE         = 'SIM_CLONE',         'Clone SIM suspecté (MSISDN simultané)'
        CROSS_BORDER      = 'CROSS_BORDER',      'Trafic transfrontalier suspect'
        BLACKLIST_CONTACT = 'BLACKLIST_CONTACT', 'Contact avec MSISDN liste noire'

    class Severity(models.TextChoices):
        LOW      = 'LOW',      'Faible'
        MEDIUM   = 'MEDIUM',   'Modéré'
        HIGH     = 'HIGH',     'Élevé'
        CRITICAL = 'CRITICAL', 'Critique'

    class AlertStatus(models.TextChoices):
        OPEN           = 'OPEN',           'Ouverte'
        INVESTIGATING  = 'INVESTIGATING',  "En cours d'investigation"
        CLOSED         = 'CLOSED',         'Fermée'
        FALSE_POSITIVE = 'FALSE_POSITIVE', 'Faux positif'

    alert_type      = models.CharField(max_length=20, choices=AlertType.choices, db_index=True)
    severity        = models.CharField(max_length=10, choices=Severity.choices)
    # Citoyen principal concerné
    national_id     = models.CharField(max_length=20, blank=True, db_index=True)
    # MSISDN(s) impliqués
    msisdn_a        = models.CharField(max_length=20, blank=True, db_index=True)
    msisdn_b        = models.CharField(max_length=20, blank=True)
    title           = models.CharField(max_length=200)
    description     = models.TextField(blank=True)
    status          = models.CharField(
        max_length=20, choices=AlertStatus.choices, default=AlertStatus.OPEN
    )
    # Preuves : IMEIs, timestamps, fréquences, etc.
    evidence        = models.JSONField(default=dict)
    created_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_comms_alerts'
    )
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['alert_type', 'severity']),
            models.Index(fields=['national_id', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
        verbose_name        = 'alerte comms'
        verbose_name_plural = 'alertes comms'

    def __str__(self):
        return f"[{self.severity}] {self.alert_type} — {self.title[:50]}"
