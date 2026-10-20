"""
Models Module 04 — Eyeshield Intel : couche renseignement.

Trois piliers :
  IntelAlert  — alerte d'anomalie ou signal faible (structuration financière,
                clusters suspects, tentatives biométriques répétées…)
  NetworkLink — arête du graphe d'identité (qui est lié à qui, et pourquoi)
  ThreatZone  — zone géographique à risque (banditisme, groupe armé, trafic…)

Accès strictement restreint : ROLE_INTEL, ROLE_POLICE, ROLE_BORDER, ROLE_ADMIN.
"""
from django.conf import settings
from django.db import models


class IntelAlert(models.Model):
    """
    Alerte de renseignement générée automatiquement ou manuellement.

    APPEND-ONLY : ne jamais DELETE ni UPDATE une alerte. Utiliser `status`
    pour la marquer résolue. L'historique est la preuve.
    """

    class AlertType(models.TextChoices):
        STRUCTURING     = 'STRUCTURING',     'Structuration financière (smurfing)'
        NETWORK         = 'NETWORK',         'Anomalie réseau (cluster suspect)'
        FREQUENCY       = 'FREQUENCY',       'Fréquence anormale de transactions'
        GEOGRAPHIC      = 'GEOGRAPHIC',      'Mouvement géographique suspect'
        BIOMETRIC       = 'BIOMETRIC',       'Tentatives biométriques répétées'
        WATCHLIST_CROSS = 'WATCHLIST_CROSS', 'Croisement watchlist multi-sources'
        MANUAL          = 'MANUAL',          'Alerte manuelle analyste'

    class Severity(models.TextChoices):
        LOW      = 'LOW',      'Faible'
        MEDIUM   = 'MEDIUM',   'Modéré'
        HIGH     = 'HIGH',     'Élevé'
        CRITICAL = 'CRITICAL', 'Critique'

    class Status(models.TextChoices):
        OPEN           = 'OPEN',           'Ouverte'
        INVESTIGATING  = 'INVESTIGATING',  "En cours d'investigation"
        CLOSED         = 'CLOSED',         'Fermée'
        FALSE_POSITIVE = 'FALSE_POSITIVE', 'Faux positif'

    # Citoyen concerné — vide pour les alertes géographiques/réseau sans sujet unique
    national_id   = models.CharField(max_length=20, blank=True, db_index=True)
    alert_type    = models.CharField(max_length=20, choices=AlertType.choices)
    severity      = models.CharField(max_length=10, choices=Severity.choices)
    title         = models.CharField(max_length=200)
    description   = models.TextField(blank=True)
    status        = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    # evidence : données brutes — montants, dates, patterns, coordonnées, etc.
    evidence      = models.JSONField(default=dict)
    # Module source : 'DATA' | 'FOUNDRY' | 'BIOMETRIC' | 'MANUAL'
    source_module = models.CharField(max_length=20, blank=True)
    assigned_to   = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_intel_alerts'
    )
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_intel_alerts'
    )
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['national_id', 'alert_type']),
            models.Index(fields=['alert_type', 'created_at']),
        ]
        verbose_name        = 'alerte intel'
        verbose_name_plural = 'alertes intel'

    def __str__(self):
        return f"[{self.severity}] {self.alert_type} — {self.title[:50]}"


class NetworkLink(models.Model):
    """
    Arête du graphe de réseau : lien entre deux national_ids.

    Chaque arête a un type (FINANCIAL, FAMILY…) et une force (0.0→1.0).
    Le graphe est NON ORIENTÉ logiquement, mais stocké orienté pour
    simplifier les requêtes — toujours créer source < target alphabétiquement
    ou chercher dans les deux sens.
    """

    class LinkType(models.TextChoices):
        FINANCIAL  = 'FINANCIAL',  'Financier (transactions communes)'
        FAMILY     = 'FAMILY',     'Familial (état civil ONEC)'
        GEOGRAPHIC = 'GEOGRAPHIC', 'Géographique (même adresse / zone)'
        TELECOM    = 'TELECOM',    'Télécom (appels / SMS communs)'
        COWORKER   = 'COWORKER',   'Professionnel (même employeur SIGA)'
        ASSOCIATE  = 'ASSOCIATE',  'Associé (connu des services)'

    source_national_id = models.CharField(max_length=20, db_index=True)
    target_national_id = models.CharField(max_length=20, db_index=True)
    link_type          = models.CharField(max_length=15, choices=LinkType.choices)
    # 0.0 = lien faible (géographique / indirect), 1.0 = lien fort (familial direct)
    strength           = models.FloatField(default=1.0)
    evidence           = models.JSONField(default=dict)
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['source_national_id', 'target_national_id', 'link_type']
        indexes = [
            models.Index(fields=['source_national_id']),
            models.Index(fields=['target_national_id']),
        ]
        verbose_name        = 'lien réseau'
        verbose_name_plural = 'liens réseau'

    def __str__(self):
        return (
            f"{self.source_national_id} ←{self.link_type}→ "
            f"{self.target_national_id} ({self.strength:.2f})"
        )


class ThreatZone(models.Model):
    """
    Zone géographique à risque — banditisme, groupe armé, trafic, fraude.

    Les coordonnées sont stockées en GeoJSON simplifié :
    [[lat, lon], [lat, lon], ...] pour un polygone ou un point unique.
    """

    class ThreatType(models.TextChoices):
        BANDITRY    = 'BANDITRY',    'Banditisme / Criminalité'
        ARMED_GROUP = 'ARMED_GROUP', 'Groupe armé'
        TRAFFICKING = 'TRAFFICKING', 'Trafic (drogues, armes, humains)'
        FRAUD       = 'FRAUD',       'Fraude financière organisée'
        TERRORISM   = 'TERRORISM',   'Terrorisme / Extrémisme'
        OTHER       = 'OTHER',       'Autre menace'

    class Severity(models.TextChoices):
        LOW      = 'LOW',      'Faible'
        MEDIUM   = 'MEDIUM',   'Modéré'
        HIGH     = 'HIGH',     'Élevé'
        CRITICAL = 'CRITICAL', 'Critique'

    class ZoneStatus(models.TextChoices):
        ACTIVE     = 'ACTIVE',     'Active'
        MONITORING = 'MONITORING', 'Sous surveillance'
        RESOLVED   = 'RESOLVED',   'Résolue'

    name        = models.CharField(max_length=150)
    province    = models.CharField(max_length=100, blank=True)
    territoire  = models.CharField(max_length=100, blank=True)
    threat_type = models.CharField(max_length=15, choices=ThreatType.choices)
    severity    = models.CharField(max_length=10, choices=Severity.choices)
    status      = models.CharField(
        max_length=12, choices=ZoneStatus.choices, default=ZoneStatus.ACTIVE
    )
    description = models.TextField(blank=True)
    # GeoJSON simplifié : [[lat, lon], ...] ou point unique [[lat, lon]]
    coordinates = models.JSONField(default=list, blank=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reported_threat_zones'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-severity', '-created_at']
        indexes  = [
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['province', 'status']),
        ]
        verbose_name        = 'zone de menace'
        verbose_name_plural = 'zones de menace'

    def __str__(self):
        return f"[{self.severity}] {self.threat_type} — {self.name} ({self.province})"
