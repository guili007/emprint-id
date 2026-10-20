"""
Citoyen RDC — identité nationale numérique.

Le `national_id` est LA clé universelle de l'écosystème Eyeshield.
Format : CG-KN-LWA-000147-X9 (pays-province-commune-séquence-checksum)
"""
import uuid
from django.db import models


class Province(models.Model):
    code = models.CharField(max_length=2, unique=True)
    nom = models.CharField(max_length=100)

    class Meta:
        ordering = ['nom']
        verbose_name = 'province'

    def __str__(self):
        return f"{self.code} — {self.nom}"


class Commune(models.Model):
    code = models.CharField(max_length=3, unique=True)
    nom = models.CharField(max_length=100)
    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name='communes')

    class Meta:
        ordering = ['nom']
        verbose_name = 'commune'

    def __str__(self):
        return f"{self.code} — {self.nom}"


class Citizen(models.Model):
    """
    Un citoyen enrôlé dans EmPrint-iD.

    `national_id` : identifiant unique de la forme CG-KN-LWA-000147-X9.
    Généré lors de l'enrôlement, jamais modifié, jamais réutilisé.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    national_id = models.CharField(max_length=20, unique=True, db_index=True)

    nom = models.CharField(max_length=100)
    postnom = models.CharField(max_length=100, blank=True)
    prenom = models.CharField(max_length=100, blank=True)

    class Sexe(models.TextChoices):
        M = 'M', 'Masculin'
        F = 'F', 'Féminin'

    sexe = models.CharField(max_length=1, choices=Sexe.choices, blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=150, blank=True)

    province = models.ForeignKey(Province, null=True, blank=True, on_delete=models.PROTECT)
    commune = models.ForeignKey(Commune, null=True, blank=True, on_delete=models.PROTECT)

    # Photo d'enrôlement — image de référence pour la vérification biométrique.
    # Jamais servie publiquement ; chiffrée au repos sur le disque.
    photo = models.ImageField(upload_to='citizens/photos/', null=True, blank=True)

    issued_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = 'citoyen'
        ordering = ['nom', 'postnom']
        indexes = [models.Index(fields=['nom', 'postnom'])]

    def __str__(self):
        return f"{self.nom} {self.postnom} — {self.national_id}"

    @property
    def nom_complet(self) -> str:
        return " ".join(p for p in [self.nom, self.postnom, self.prenom] if p)
