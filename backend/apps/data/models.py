"""
Models Module 02 — Eyeshield Data : couche ontologie.

Principe Palantir : chaque citoyen possède un national_id EmPrint-iD unique
qui relie toutes les sources externes (DGI, ARDHI, Rawbank, ONEC, Santé…).
CitizenDataLink est le nœud central de ce graphe d'identité.
"""
from django.conf import settings
from django.db import models


class DataSource(models.Model):
    """
    Source de données externe reconnue par Eyeshield Data.

    Exemples : DGI (impôts), RAWBANK (comptes), ARDHI (foncier), SIGA (fonctionnaires).
    Chaque source a un secteur qui détermine les droits d'accès par rôle.
    """

    class Sector(models.TextChoices):
        FISCAL       = 'FISCAL',        'Fiscal (DGI / impôts)'
        BANKING      = 'BANKING',       'Bancaire (Rawbank, équivalents)'
        CIVIL        = 'CIVIL',         'État civil (ONEC)'
        LAND         = 'LAND',          'Foncier (ARDHI)'
        HEALTH       = 'HEALTH',        'Santé (Ministère, hôpitaux)'
        EDUCATION    = 'EDUCATION',     'Éducation (EduFirst, Cachet)'
        PUBLIC_SVC   = 'PUBLIC_SVC',    'Fonction publique (SIGA)'
        TELECOM      = 'TELECOM',       'Télécommunications (Airtel, Orange)'
        JUSTICE      = 'JUSTICE',       'Justice / Sécurité (DGM, Interpol)'
        IDENTITY     = 'IDENTITY',      'Identité (EmPrint-iD interne)'

    code        = models.CharField(max_length=20, unique=True)
    name        = models.CharField(max_length=100)
    sector      = models.CharField(max_length=20, choices=Sector.choices)
    description = models.TextField(blank=True)
    api_url     = models.URLField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sector', 'code']
        verbose_name        = 'source de données'
        verbose_name_plural = 'sources de données'

    def __str__(self):
        return f"{self.code} ({self.get_sector_display()})"


class CitizenDataLink(models.Model):
    """
    Lien ontologie : national_id EmPrint-iD ↔ identifiant dans une source externe.

    APPEND-ONLY en pratique : ne jamais supprimer un lien vérifié.
    Pour désactiver un lien, préférer metadata={'active': False}.
    """

    national_id = models.CharField(max_length=20, db_index=True)
    source      = models.ForeignKey(
        DataSource, on_delete=models.CASCADE, related_name='links'
    )
    external_id = models.CharField(max_length=150)
    label       = models.CharField(max_length=250, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='verified_data_links'
    )
    # Métadonnées libres : score de confiance, date de sync, source brute, etc.
    metadata    = models.JSONField(default=dict, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['national_id', 'source']
        indexes = [
            models.Index(fields=['national_id']),
            models.Index(fields=['source', 'external_id']),
        ]
        verbose_name        = 'lien données citoyen'
        verbose_name_plural = 'liens données citoyen'

    def __str__(self):
        return f"{self.national_id} → {self.source.code}:{self.external_id}"


class DataAccessPolicy(models.Model):
    """
    Contrôle d'accès granulaire : quel SectorTenant peut lire quelle DataSource.

    Complète le RBAC par rôle avec un ABAC par organisation.
    Ex : Rawbank (BANKING) peut lire les sources BANKING + IDENTITY.
    """

    # FK croisée vers apps.foundry — le label Django de cette app est `foundry`
    tenant = models.ForeignKey(
        'foundry.SectorTenant',
        on_delete=models.CASCADE, related_name='data_policies'
    )
    source    = models.ForeignKey(
        DataSource, on_delete=models.CASCADE, related_name='access_policies'
    )
    can_read  = models.BooleanField(default=False)
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='granted_data_policies'
    )

    class Meta:
        unique_together = ['tenant', 'source']
        verbose_name        = "politique d'accès"
        verbose_name_plural = "politiques d'accès"

    def __str__(self):
        flag = "✓" if self.can_read else "✗"
        return f"{self.tenant.name} {flag} → {self.source.code}"
