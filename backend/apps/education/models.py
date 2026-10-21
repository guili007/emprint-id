"""
Models Module 10 — Eyeshield Education : registre scolaire national.

Quatre piliers :
  StudentRecord  — dossier scolaire (clé métier = national_id + year)
  AcademicResult — résultats APPEND-ONLY
  Diploma        — diplôme national APPEND-ONLY (numero_certificat unique)
  SchoolAlert    — alertes d'abandon/vulnérabilité (statut mutable)

Invariants :
  AcademicResult, Diploma : jamais DELETE ni UPDATE.
  SchoolAlert.statut est mutable (OUVERT → RESOLU / ARCHIVE).
  Diploma.numero_certificat doit être unique (attestation légale anti-fraude).
"""
from django.conf import settings
from django.db import models


class StudentRecord(models.Model):
    """
    Dossier scolaire annuel — un enregistrement par (national_id, school_year).
    Le statut est mutable (ACTIF → DIPLOME / ABANDONNE / TRANSFERE).
    """

    class Statut(models.TextChoices):
        ACTIF     = 'ACTIF',     'Actif'
        DIPLOME   = 'DIPLOME',   'Diplômé'
        ABANDONNE = 'ABANDONNE', 'Abandonné'
        TRANSFERE = 'TRANSFERE', 'Transféré'

    class NiveauScolaire(models.TextChoices):
        PRESCOLAIRE  = 'PRESCOLAIRE',  'Préscolaire'
        PRIMAIRE     = 'PRIMAIRE',     'Primaire'
        SECONDAIRE   = 'SECONDAIRE',   'Secondaire'
        SUPERIEUR    = 'SUPERIEUR',    'Supérieur'
        FORMATION_PRO= 'FORMATION_PRO','Formation professionnelle'

    national_id    = models.CharField(max_length=20, db_index=True)
    school_year    = models.CharField(max_length=9, db_index=True)   # ex: "2023-2024"
    niveau         = models.CharField(max_length=15, choices=NiveauScolaire.choices)
    classe         = models.CharField(max_length=50)                  # ex: "6ème primaire"
    etablissement  = models.CharField(max_length=200)
    province       = models.CharField(max_length=100, db_index=True)
    statut         = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ACTIF, db_index=True)
    created_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='student_records_created'
    )
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        # Un élève ne peut avoir qu'un seul dossier par année scolaire
        unique_together     = [('national_id', 'school_year')]
        ordering            = ['-school_year']
        verbose_name        = 'dossier scolaire'
        verbose_name_plural = 'dossiers scolaires'

    def __str__(self):
        return f"{self.national_id} — {self.classe} ({self.school_year})"


class AcademicResult(models.Model):
    """Résultats scolaires annuels — APPEND-ONLY."""

    class Mention(models.TextChoices):
        ECHEC              = 'ECHEC',              'Échec'
        PASSABLE           = 'PASSABLE',           'Passable'
        SATISFACTION       = 'SATISFACTION',       'Satisfaction'
        DISTINCTION        = 'DISTINCTION',        'Distinction'
        GRANDE_DISTINCTION = 'GRANDE_DISTINCTION', 'Grande Distinction'
        MAX_DES_POINTS     = 'MAX_DES_POINTS',     'Maximum des points'

    student   = models.ForeignKey(StudentRecord, on_delete=models.CASCADE, related_name='results')
    matiere   = models.CharField(max_length=100)
    note      = models.DecimalField(max_digits=5, decimal_places=2)   # sur 100
    note_max  = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    mention   = models.CharField(max_length=20, choices=Mention.choices)
    agent     = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='academic_results_recorded'
    )
    created_at= models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['matiere']
        verbose_name        = 'résultat scolaire'
        verbose_name_plural = 'résultats scolaires'

    def __str__(self):
        return f"{self.matiere} — {self.note}/{self.note_max} ({self.mention})"


class Diploma(models.Model):
    """Diplôme national — APPEND-ONLY. numero_certificat unique = anti-fraude."""

    class TypeDiplome(models.TextChoices):
        CERTIFICAT_PRIMAIRE   = 'CERT_PRIM',  "Certificat d'études primaires"
        DIPLOME_ETAT          = 'DIPL_ETAT',  "Diplôme d'État (secondaire)"
        LICENCE               = 'LICENCE',    'Licence'
        MASTER                = 'MASTER',     'Master'
        DOCTORAT              = 'DOCTORAT',   'Doctorat'
        BREVET_PROFESSIONNEL  = 'BREVET_PRO', 'Brevet professionnel'

    national_id        = models.CharField(max_length=20, db_index=True)
    type_diplome       = models.CharField(max_length=10, choices=TypeDiplome.choices, db_index=True)
    etablissement      = models.CharField(max_length=200)
    province           = models.CharField(max_length=100)
    annee_obtention    = models.PositiveSmallIntegerField(db_index=True)
    # Numéro de série officiel — unique pour éviter la fraude documentaire
    numero_certificat  = models.CharField(max_length=50, unique=True, db_index=True)
    mention            = models.CharField(max_length=20, blank=True)
    created_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='diplomas_recorded'
    )
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['-annee_obtention']
        indexes             = [
            models.Index(fields=['national_id', 'type_diplome']),
        ]
        verbose_name        = 'diplôme'
        verbose_name_plural = 'diplômes'

    def __str__(self):
        return f"{self.type_diplome} — {self.national_id} ({self.annee_obtention})"


class SchoolAlert(models.Model):
    """
    Alerte scolaire — abandon, vulnérabilité, comportement.
    statut est mutable : OUVERT → RESOLU / ARCHIVE.
    """

    class AlertType(models.TextChoices):
        ABANDON       = 'ABANDON',       'Risque d\'abandon'
        COMPORTEMENT  = 'COMPORTEMENT',  'Problème comportemental'
        VULNERABLE    = 'VULNERABLE',    'Élève vulnérable'
        DIPLOME_FAUX  = 'DIPLOME_FAUX',  'Suspicion diplôme frauduleux'
        AUTRE         = 'AUTRE',         'Autre'

    class Statut(models.TextChoices):
        OUVERT  = 'OUVERT',  'Ouvert'
        RESOLU  = 'RESOLU',  'Résolu'
        ARCHIVE = 'ARCHIVE', 'Archivé'

    class Severity(models.TextChoices):
        FAIBLE   = 'FAIBLE',   'Faible'
        MODERE   = 'MODERE',   'Modéré'
        ELEVE    = 'ELEVE',    'Élevé'
        CRITIQUE = 'CRITIQUE', 'Critique'

    national_id  = models.CharField(max_length=20, db_index=True)
    alert_type   = models.CharField(max_length=15, choices=AlertType.choices, db_index=True)
    severity     = models.CharField(max_length=8, choices=Severity.choices, default=Severity.MODERE)
    description  = models.TextField()
    statut       = models.CharField(max_length=8, choices=Statut.choices, default=Statut.OUVERT, db_index=True)
    issued_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='school_alerts_issued'
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['-created_at']
        indexes             = [
            models.Index(fields=['national_id', 'statut']),
        ]
        verbose_name        = 'alerte scolaire'
        verbose_name_plural = 'alertes scolaires'

    def __str__(self):
        return f"[{self.alert_type}] {self.national_id} — {self.severity} ({self.statut})"
