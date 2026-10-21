"""
Models Module 09 — Eyeshield Health : dossiers médicaux + vaccination + épidémio.

Cinq piliers :
  HealthPatient    — dossier médical unifié (clé métier = national_id)
  HealthVisit      — consultation APPEND-ONLY
  HealthVaccination— carnet vaccinal APPEND-ONLY
  HealthPrescription — ordonnance APPEND-ONLY
  EpidemioAlert    — alerte épidémiologique (Ebola, choléra, mpox…)

Invariants :
  HealthVisit, HealthVaccination, HealthPrescription : jamais DELETE ni UPDATE.
  EpidemioAlert.status est mutable (EN_COURS → RESOLU / SURVEILLE).
"""
from django.conf import settings
from django.db import models


class HealthPatient(models.Model):
    """
    Dossier médical unifié — lié à l'identité nationale EmPrint-iD.
    Un national_id = un HealthPatient.
    """

    class BloodType(models.TextChoices):
        A_POS  = 'A+',  'A+'
        A_NEG  = 'A-',  'A-'
        B_POS  = 'B+',  'B+'
        B_NEG  = 'B-',  'B-'
        AB_POS = 'AB+', 'AB+'
        AB_NEG = 'AB-', 'AB-'
        O_POS  = 'O+',  'O+'
        O_NEG  = 'O-',  'O-'

    national_id          = models.CharField(max_length=20, unique=True, db_index=True)
    blood_type           = models.CharField(max_length=3, choices=BloodType.choices, blank=True)
    # Listes JSON : ["pénicilline", "arachides"]
    allergies            = models.JSONField(default=list)
    chronic_conditions   = models.JSONField(default=list)
    created_by           = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='health_patients_created'
    )
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'dossier médical'
        verbose_name_plural = 'dossiers médicaux'

    def __str__(self):
        return f"Patient {self.national_id} ({self.blood_type or 'groupe inconnu'})"


class HealthVisit(models.Model):
    """Consultation médicale — APPEND-ONLY."""

    class VisitType(models.TextChoices):
        CONSULTATION    = 'CONSULTATION',    'Consultation'
        HOSPITALISATION = 'HOSPITALISATION', 'Hospitalisation'
        URGENCE         = 'URGENCE',         'Urgence'
        TELECONSULT     = 'TELECONSULT',     'Téléconsultation'

    patient           = models.ForeignKey(HealthPatient, on_delete=models.CASCADE, related_name='visits')
    agent             = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='health_visits_recorded'
    )
    facility_name     = models.CharField(max_length=200)
    visit_type        = models.CharField(max_length=15, choices=VisitType.choices)
    motif             = models.CharField(max_length=300)
    # Code ICD-10 optionnel : A09, B01.9…
    diagnostic_code   = models.CharField(max_length=10, blank=True, db_index=True)
    diagnostic_label  = models.CharField(max_length=300, blank=True)
    date_visite       = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-date_visite']
        indexes  = [
            models.Index(fields=['patient', 'date_visite']),
        ]
        verbose_name        = 'consultation'
        verbose_name_plural = 'consultations'

    def __str__(self):
        return f"[{self.visit_type}] {self.patient.national_id} — {self.date_visite:%Y-%m-%d}"


class HealthVaccination(models.Model):
    """Acte de vaccination — APPEND-ONLY (carnet vaccinal)."""

    patient            = models.ForeignKey(HealthPatient, on_delete=models.CASCADE, related_name='vaccinations')
    vaccin_nom         = models.CharField(max_length=100)
    # Codes standardisés : BCG, VPHB, RR, VPO, DTC, YELLOW_FEVER…
    vaccin_code        = models.CharField(max_length=20, db_index=True)
    dose_numero        = models.PositiveSmallIntegerField(default=1)
    date_administration= models.DateField(db_index=True)
    lot_numero         = models.CharField(max_length=50, blank=True)
    facility_name      = models.CharField(max_length=200)
    agent              = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='vaccinations_recorded'
    )

    class Meta:
        ordering = ['-date_administration']
        indexes  = [
            models.Index(fields=['patient', 'vaccin_code']),
        ]
        verbose_name        = 'vaccination'
        verbose_name_plural = 'vaccinations'

    def __str__(self):
        return f"{self.vaccin_code} dose {self.dose_numero} — {self.patient.national_id}"


class HealthPrescription(models.Model):
    """Ordonnance médicale — APPEND-ONLY."""

    patient           = models.ForeignKey(HealthPatient, on_delete=models.CASCADE, related_name='prescriptions')
    # Lien optionnel vers la consultation qui a généré l'ordonnance
    visit             = models.ForeignKey(
        HealthVisit, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='prescriptions'
    )
    medicament_nom    = models.CharField(max_length=200)
    # Ex : "2×/jour pendant 7 jours"
    posologie         = models.CharField(max_length=200)
    prescrit_par      = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='prescriptions_issued'
    )
    facility_name     = models.CharField(max_length=200)
    date_prescription = models.DateField(auto_now_add=True, db_index=True)
    est_delivre       = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date_prescription']
        verbose_name        = 'prescription'
        verbose_name_plural = 'prescriptions'

    def __str__(self):
        return f"{self.medicament_nom} — {self.patient.national_id} ({self.date_prescription})"


class EpidemioAlert(models.Model):
    """
    Alerte épidémiologique — émise par le Ministère de la Santé ou l'OMS.
    status est mutable : EN_COURS → RESOLU / SURVEILLE.
    """

    class Niveau(models.TextChoices):
        FAIBLE   = 'FAIBLE',   'Faible'
        MODERE   = 'MODERE',   'Modéré'
        ELEVE    = 'ELEVE',    'Élevé'
        CRITIQUE = 'CRITIQUE', 'Critique'

    class Statut(models.TextChoices):
        EN_COURS  = 'EN_COURS',  'En cours'
        RESOLU    = 'RESOLU',    'Résolu'
        SURVEILLE = 'SURVEILLE', 'Sous surveillance'

    disease_code   = models.CharField(max_length=20, db_index=True)
    disease_name   = models.CharField(max_length=100)
    province       = models.CharField(max_length=100, db_index=True)
    territoire     = models.CharField(max_length=100, blank=True)
    cas_confirmes  = models.PositiveIntegerField(default=0)
    cas_suspects   = models.PositiveIntegerField(default=0)
    deces          = models.PositiveIntegerField(default=0)
    date_debut     = models.DateField(db_index=True)
    date_fin       = models.DateField(null=True, blank=True)
    niveau         = models.CharField(max_length=8, choices=Niveau.choices, default=Niveau.MODERE)
    statut         = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_COURS, db_index=True)
    # Source : "OMS", "Ministère Santé RDC", "INRB"…
    source         = models.CharField(max_length=100, blank=True)
    created_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='epidemio_alerts_created'
    )
    created_at     = models.DateTimeField(auto_now_add=True)

    @property
    def taux_letalite(self) -> float:
        """Taux de létalité = décès / cas confirmés × 100."""
        if self.cas_confirmes == 0:
            return 0.0
        return round(self.deces / self.cas_confirmes * 100, 2)

    class Meta:
        ordering = ['-date_debut']
        indexes  = [
            models.Index(fields=['statut', 'date_debut']),
            models.Index(fields=['province', 'statut']),
        ]
        verbose_name        = 'alerte épidémiologique'
        verbose_name_plural = 'alertes épidémiologiques'

    def __str__(self):
        return f"[{self.disease_name}] {self.province} — {self.niveau} ({self.statut})"
