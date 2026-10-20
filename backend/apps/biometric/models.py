"""
Module biométrique EmPrint-iD.

Trois tables :
- CitizenFaceEmbedding  : vecteur ArcFace 512D stocké via pgvector (1:1 citoyen)
- WatchlistEntry        : personnes sous surveillance (rouge / orange / jaune)
- VerificationLog       : audit immuable de chaque vérification (JAMAIS de DELETE)
"""
from django.conf import settings
from django.db import models

from apps.citizens.models import Citizen


class AgentProfile(models.Model):
    """Rôle métier de l'agent terrain (1:1 avec User)."""

    class Role(models.TextChoices):
        POLICE = 'ROLE_POLICE', 'Police Nationale'
        BANK = 'ROLE_BANK', 'Banque / KYC'
        BORDER = 'ROLE_BORDER', 'Contrôle Frontière'
        HEALTH = 'ROLE_HEALTH', 'Santé'
        ADMIN = 'ROLE_ADMIN', 'Administrateur'
        WATCHLIST_ADMIN = 'ROLE_WATCHLIST_ADMIN', 'Admin Watchlist'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile'
    )
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.ADMIN)

    class Meta:
        verbose_name = "profil agent"

    def __str__(self):
        return f"{self.user.username} [{self.role}]"


class CitizenFaceEmbedding(models.Model):
    """
    Embedding facial ArcFace (512 dimensions) pour la recherche 1:N.

    Dev : stocké en JSONField (liste Python → JSON).
    Prod Linux : migrer vers VectorField(dimensions=512) + pgvector.
    Séparé du modèle Citizen pour pouvoir migrer sans toucher à l'identité.
    """
    citizen = models.OneToOneField(
        Citizen, on_delete=models.CASCADE, related_name='face_embedding'
    )
    # Stockage dev : list[float] de 512 valeurs sérialisé en JSON
    embedding = models.JSONField(default=list)
    model_version = models.CharField(max_length=50, default='ArcFace-r100')
    liveness_score = models.FloatField(null=True, blank=True)
    quality_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "embedding facial"

    def __str__(self):
        return f"Embedding — {self.citizen.national_id}"


class WatchlistEntry(models.Model):
    """
    Entrée sur la liste de surveillance.

    Seul un compte avec rôle WATCHLIST_ADMIN peut écrire ici.
    Les agents terrain ne font que lire (via l'endpoint de vérification).
    """

    class AlertLevel(models.TextChoices):
        ROUGE = 'ROUGE', 'Danger immédiat'
        ORANGE = 'ORANGE', 'Surveillance active'
        JAUNE = 'JAUNE', 'Information'

    class Authority(models.TextChoices):
        CIVIL = 'CIVIL', 'Autorité civile (Gouvernement / Police)'
        MILITAIRE = 'MILITAIRE', 'Forces armées (FARDC / Défense)'
        ETAT = 'ETAT', 'État — diffusion générale (civil + militaire)'

    citizen = models.ForeignKey(Citizen, on_delete=models.PROTECT, related_name='watchlist_entries')
    alert_level = models.CharField(max_length=10, choices=AlertLevel.choices)
    authority = models.CharField(
        max_length=15,
        choices=Authority.choices,
        default=Authority.CIVIL,
        help_text="Détermine quel dashboard reçoit l'alerte silencieuse.",
    )
    reason = models.TextField()
    issued_by = models.CharField(max_length=100, help_text="PNC, FARDC, BCC, Justice, INTERPOL…")
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='watchlist_entries_created'
    )

    class Meta:
        verbose_name = "entrée watchlist"
        indexes = [
            models.Index(fields=['citizen', 'is_active']),
            models.Index(fields=['alert_level', 'is_active']),
        ]

    def __str__(self):
        return f"[{self.alert_level}] {self.citizen.national_id} — {self.issued_by}"


class VerificationLog(models.Model):
    """
    Journal immuable de toutes les vérifications biométriques.

    Règle absolue : jamais de DELETE, jamais de UPDATE sur cette table.
    Elle est la preuve légale que la vérification a eu lieu.
    Aucune image ou embedding n'est stocké ici (voir règle sécurité §10.8).
    """

    class VerifStatus(models.TextChoices):
        VERIFIED = 'VERIFIED', 'Identité confirmée'
        REJECTED_FACE = 'REJECTED_FACE', 'Visage non reconnu'
        REJECTED_LIVENESS = 'REJECTED_LIVENESS', 'Liveness échoué (fraude ?)'
        REJECTED_WATCHLIST = 'REJECTED_WATCHLIST', 'Sur la watchlist'
        ERROR = 'ERROR', 'Erreur technique'

    citizen = models.ForeignKey(
        Citizen, null=True, blank=True, on_delete=models.PROTECT, related_name='verification_logs'
    )
    agent_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='verifications_done'
    )
    status = models.CharField(max_length=30, choices=VerifStatus.choices)
    confidence_score = models.FloatField(null=True, blank=True)
    liveness_score = models.FloatField(null=True, blank=True)
    watchlist_hit = models.ForeignKey(
        WatchlistEntry, null=True, blank=True, on_delete=models.PROTECT
    )
    agent_role = models.CharField(max_length=30, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "log de vérification"
        # Pas d'index sur citizen seul : la recherche se fait toujours par
        # timestamp ou par combinaison (citizen + timestamp).
        indexes = [models.Index(fields=['citizen', 'timestamp'])]

    def __str__(self):
        return f"{self.status} — {self.timestamp:%Y-%m-%d %H:%M}"
