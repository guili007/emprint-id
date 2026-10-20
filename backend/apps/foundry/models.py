"""
Module 03 — Eyeshield Foundry.

Modèles :
  Sector        : BANKING | GOV | HEALTH | EDU
  SectorTenant  : organisation abonnée (Rawbank, Ministère Finance, etc.)
  FraudAlert    : alerte fraude inter-bancaire (même ID dans N banques simultanément)

  --- Gov (SIGA cache) ---
  GovEmployee      : snapshot d'un agent de la fonction publique (source : SIGA-RDC)
  GovCareerEvent   : snapshot événement de carrière (promotion, mutation, retraite…)
  GovBudgetLine    : ligne de budget public par ministère (données mock v1)
  GovContract      : marché public (données mock v1)
"""
import uuid

from django.conf import settings
from django.db import models


class Sector(models.TextChoices):
    BANKING = 'BANKING', 'Eyeshield Banking'
    GOV     = 'GOV',     'Eyeshield Gov'
    HEALTH  = 'HEALTH',  'Eyeshield Health'
    EDU     = 'EDU',     'Eyeshield Edu'


class SectorTenant(models.Model):
    """
    Organisation abonnée à un secteur Foundry.

    Exemples : Rawbank (BANKING), Ministère des Finances (GOV),
               Hôpital Général de Kinshasa (HEALTH), EduFirst (EDU).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, unique=True)
    sector = models.CharField(max_length=10, choices=Sector.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    api_key_hash = models.CharField(
        max_length=64, unique=True, null=True, blank=True, default=None,
        help_text="SHA-256 de la clé API SaaS — jamais en clair."
    )

    class Meta:
        verbose_name = "tenant Foundry"
        ordering = ['sector', 'name']

    def __str__(self):
        return f"[{self.sector}] {self.name}"


class TenantAgent(models.Model):
    """
    Lie un compte User EmPrint-iD à un tenant Foundry.
    Un agent peut appartenir à plusieurs tenants (ex. admin groupe bancaire).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_memberships'
    )
    tenant = models.ForeignKey(SectorTenant, on_delete=models.CASCADE, related_name='agents')
    is_admin = models.BooleanField(
        default=False,
        help_text="Admin du tenant — peut voir les alertes fraude et les stats du secteur."
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'tenant')]
        verbose_name = "agent tenant"

    def __str__(self):
        return f"{self.user.username} → {self.tenant.name}"


class FraudAlert(models.Model):
    """
    Alerte fraude inter-bancaire.

    Déclenchée quand le même national_id est vérifié par ≥ N tenants
    distincts dans une fenêtre de temps configurable.
    """

    class Severity(models.TextChoices):
        HIGH   = 'HIGH',   'Critique — même ID dans 5+ banques'
        MEDIUM = 'MEDIUM', 'Élevée — même ID dans 3-4 banques'
        LOW    = 'LOW',    'Faible — même ID dans 2 banques'

    national_id = models.CharField(max_length=20, db_index=True)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    tenant_count = models.PositiveSmallIntegerField(
        help_text="Nombre de tenants distincts ayant vérifié cet ID dans la fenêtre."
    )
    tenant_names = models.JSONField(
        default=list,
        help_text="Liste des noms de tenants impliqués."
    )
    window_minutes = models.PositiveSmallIntegerField(default=60)
    detected_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='resolved_fraud_alerts'
    )

    class Meta:
        verbose_name = "alerte fraude"
        indexes = [
            models.Index(fields=['national_id', 'detected_at']),
            models.Index(fields=['is_resolved', 'detected_at']),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.national_id} × {self.tenant_count} banques"


class KYCRecord(models.Model):
    """
    Journal immuable des vérifications KYC par tenant bancaire.

    Utilisé pour la détection de fraude inter-bancaire :
    si le même national_id apparaît dans ≥ 2 tenants sur la fenêtre,
    un FraudAlert est créé automatiquement.
    """

    class KYCStatus(models.TextChoices):
        CONFORME     = 'CONFORME',     'Identité confirmée'
        NON_CONFORME = 'NON_CONFORME', 'Identité non confirmée'

    national_id = models.CharField(max_length=20, db_index=True)
    tenant = models.ForeignKey(
        SectorTenant, on_delete=models.CASCADE, related_name='kyc_records'
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='kyc_records'
    )
    status = models.CharField(max_length=15, choices=KYCStatus.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "enregistrement KYC"
        indexes = [
            models.Index(fields=['national_id', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
        ]

    def __str__(self):
        return f"KYC {self.status} — {self.national_id} @ {self.tenant.name}"


# ── GOV — Cache SIGA ──────────────────────────────────────────────────────────
#
# SIGA-RDC (E:\siga-rdc) est un projet SÉPARÉ qui gère les carrières des
# fonctionnaires congolais. Il expose une API REST avec SessionAuthentication.
# Plutôt que d'appeler SIGA en temps réel (fragile si SIGA est down), on
# maintient ici un CACHE LOCAL mis à jour périodiquement par `sync_siga`.
#
# Règle : on ne génère pas de données ici. On REFLÈTE ce que dit SIGA.
# Si une donnée est absente de SIGA, elle est absente ici.


class GovEmployee(models.Model):
    """
    Snapshot d'un agent de la fonction publique congolaise.

    Source : SIGA-RDC /api/v1/agents/ (lecture seule).
    Clé de réconciliation : `siga_uuid` = le public_id de l'Agent dans SIGA.

    `synced_at` : timestamp de la dernière synchro via `sync_siga`.
    Si `synced_at` est vieux (> 24h), les données sont peut-être obsolètes —
    c'est à l'opérateur de relancer la commande de sync.
    """

    class Statut(models.TextChoices):
        # Miroir exact de StatutAgent dans SIGA (apps/agents/models.py)
        EN_ENROLEMENT  = 'EN_ENROLEMENT',  "En cours d'enrôlement"
        ACTIF          = 'ACTIF',          'Actif'
        SUSPENDU       = 'SUSPENDU',       'Suspendu'
        DETACHEMENT    = 'DETACHEMENT',    'En détachement'
        DISPONIBILITE  = 'DISPONIBILITE',  'En disponibilité'
        RETRAITE       = 'RETRAITE',       'Retraité'
        RADIE          = 'RADIE',          'Radié'
        DECEDE         = 'DECEDE',         'Décédé'

    # Identifiant dans SIGA — jamais généré ici
    siga_uuid = models.UUIDField(unique=True, db_index=True)

    # Identifiant officiel (attribué par le Ministre, vient du FRAP)
    matricule = models.CharField(max_length=30, unique=True)

    # Identité (reflétée depuis SIGA, la vérité appartient au FRAP)
    nom = models.CharField(max_length=100)
    postnom = models.CharField(max_length=100, blank=True)
    prenom = models.CharField(max_length=100, blank=True)
    sexe = models.CharField(max_length=1, blank=True)

    # État courant (dénormalisé depuis le dernier événement de carrière dans SIGA)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.ACTIF)

    # Grade actuel (code = clé de référence dans SIGA, ex. 'DIR1')
    grade_code = models.CharField(max_length=20, blank=True)
    grade_libelle = models.CharField(max_length=120, blank=True)

    # Unité administrative actuelle (bureau, direction, etc.)
    unite_nom = models.CharField(max_length=200, blank=True)
    unite_type = models.CharField(max_length=20, blank=True)

    # Ministère de rattachement (racine de l'arbre administratif dans SIGA)
    administration_nom = models.CharField(max_length=200, blank=True)

    # Placeholder Cachet — sera mis à True quand Cachet sera buildé et intégré
    has_diplome_verifie = models.BooleanField(
        default=False,
        help_text="Diplôme vérifié via Cachet (placeholder — Cachet non encore buildé)."
    )

    # Timestamp de la dernière synchro via `python manage.py sync_siga`
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "fonctionnaire (cache Gov)"
        ordering = ['nom', 'postnom']
        indexes = [
            models.Index(fields=['statut']),
            models.Index(fields=['administration_nom']),
        ]

    def __str__(self):
        return f"{self.matricule} — {self.nom} {self.postnom} ({self.statut})"


class GovCareerEvent(models.Model):
    """
    Snapshot d'un événement de carrière (promotion, mutation, retraite…).

    Reflète les CareerEvent de SIGA. Append-only : on n'écrase jamais
    un événement passé, on ajoute les nouveaux lors de chaque synchro.
    """

    # Types d'événements — miroir de TypeEvenement dans SIGA
    class TypeEvenement(models.TextChoices):
        ENROLEMENT          = 'ENROLEMENT',          'Enrôlement'
        ATTRIBUTION_MATRICULE = 'ATTRIBUTION_MATRICULE', 'Attribution matricule'
        PRISE_FONCTION      = 'PRISE_FONCTION',      'Prise de fonction'
        PROMOTION           = 'PROMOTION',           'Promotion'
        MUTATION            = 'MUTATION',            'Mutation'
        SUSPENSION          = 'SUSPENSION',          'Suspension'
        REACTIVATION        = 'REACTIVATION',        'Réactivation'
        MISE_DISPONIBILITE  = 'MISE_DISPONIBILITE',  'Mise en disponibilité'
        DETACHEMENT         = 'DETACHEMENT',         'Détachement'
        RETRAITE            = 'RETRAITE',            'Retraite'
        RADIATION           = 'RADIATION',           'Radiation'
        DECES               = 'DECES',               'Décès'

    employee = models.ForeignKey(
        GovEmployee, on_delete=models.CASCADE, related_name='career_events'
    )
    type_evenement = models.CharField(max_length=25, choices=TypeEvenement.choices)

    # Date légale de l'acte (pas la date d'enregistrement dans SIGA)
    date_effet = models.DateField()

    # Rempli seulement sur PROMOTION
    grade_code = models.CharField(max_length=20, blank=True)

    # Rempli seulement sur MUTATION
    unite_nom = models.CharField(max_length=200, blank=True)

    # Référence du décret ou de l'arrêté ministériel
    reference_acte = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "événement de carrière (cache Gov)"
        ordering = ['-date_effet']

    def __str__(self):
        return f"{self.type_evenement} — {self.employee.matricule} ({self.date_effet})"


class GovBudgetLine(models.Model):
    """
    Ligne de budget public par ministère.

    Données MOCK pour v1. La vraie intégration (DGRAD, Trésor public)
    viendra dans une version ultérieure quand un export officiel sera disponible.

    `taux_execution` : ratio montant_execute / montant_alloue, en pourcentage.
    """
    annee = models.PositiveSmallIntegerField()
    ministere = models.CharField(max_length=200)

    # Intitulé du programme budgétaire (ex. "Fonctionnement courant", "Investissement")
    poste_budgetaire = models.CharField(max_length=200)

    # Montants en francs congolais (CDF)
    montant_alloue = models.DecimalField(max_digits=18, decimal_places=2)
    montant_execute = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        verbose_name = "ligne budgétaire"
        ordering = ['-annee', 'ministere']
        indexes = [
            models.Index(fields=['annee', 'ministere']),
        ]

    @property
    def taux_execution(self):
        """Taux d'exécution en % (0 si aucune allocation)."""
        if not self.montant_alloue:
            return 0
        return round(float(self.montant_execute) / float(self.montant_alloue) * 100, 1)

    def __str__(self):
        return f"{self.annee} / {self.ministere} / {self.poste_budgetaire}"


class GovContract(models.Model):
    """
    Marché public — contrat État–fournisseur.

    Données MOCK pour v1. La vérification fournisseur via EmPrint-iD
    se fait via `fournisseur_national_id` (croisement avec Citizen).
    """

    class Statut(models.TextChoices):
        EN_COURS  = 'EN_COURS',  'En cours'
        ATTRIBUE  = 'ATTRIBUE',  'Attribué'
        RESILIE   = 'RESILIE',   'Résilié'

    # Numéro de référence officiel du marché (ex. "MINECO/2026/001")
    reference = models.CharField(max_length=60, unique=True)
    objet = models.TextField()

    # Fournisseur
    fournisseur_nom = models.CharField(max_length=200)

    # National ID du fournisseur — permet de croiser avec Citizen dans EmPrint-iD
    # pour vérifier son identité biométrique avant de lui attribuer un marché
    fournisseur_national_id = models.CharField(max_length=20, blank=True, db_index=True)

    # Montant en CDF
    montant = models.DecimalField(max_digits=18, decimal_places=2)

    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_COURS)
    ministere = models.CharField(max_length=200)
    date_attribution = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "marché public"
        ordering = ['-date_attribution']

    def __str__(self):
        return f"{self.reference} — {self.fournisseur_nom} ({self.statut})"


# ── HEALTH — Eyeshield Health ──────────────────────────────────────────────────
#
# Module 03 Health : dossier patient unifié, lié à l'ID national EmPrint-iD.
# Aucun logiciel hospitalier externe pour v1 — système autonome.
#
# Règle immuabilité : HealthVisit, HealthVaccination, HealthPrescription
# ne doivent JAMAIS être supprimées ni modifiées après création.
# Même principe que VerificationLog et KYCRecord.


class HealthPatient(models.Model):
    """
    Dossier patient unifié.

    Clé métier : `national_id` = identifiant EmPrint-iD du citoyen.
    Chaque dossier est créé la première fois qu'un agent Health enregistre
    une visite pour ce citoyen (`get_or_create` dans HealthVisitView).

    Les données sensibles (embedding biométrique, photo) restent dans EmPrint-iD.
    Ce dossier ne contient que des informations médicales de base.
    """

    class BloodType(models.TextChoices):
        A_POS  = 'A+',  'A positif'
        A_NEG  = 'A-',  'A négatif'
        B_POS  = 'B+',  'B positif'
        B_NEG  = 'B-',  'B négatif'
        AB_POS = 'AB+', 'AB positif'
        AB_NEG = 'AB-', 'AB négatif'
        O_POS  = 'O+',  'O positif'
        O_NEG  = 'O-',  'O négatif'

    # Identifiant du citoyen dans EmPrint-iD (pas de FK — registre séparé)
    national_id = models.CharField(max_length=20, unique=True, db_index=True)

    blood_type = models.CharField(
        max_length=3, choices=BloodType.choices, blank=True,
        help_text="Groupe sanguin ABO/Rhésus."
    )

    # Allergies connues : list[str] — ex. ["Pénicilline", "Arachides"]
    allergies = models.JSONField(default=list, blank=True)

    # Pathologies chroniques : list[str] — ex. ["Diabète type 2", "HTA"]
    chronic_conditions = models.JSONField(default=list, blank=True)

    # Établissement qui a créé le dossier (SET_NULL si l'établissement est supprimé)
    created_by_facility = models.ForeignKey(
        SectorTenant, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_patients',
        limit_choices_to={'sector': 'HEALTH'},
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "dossier patient"
        ordering = ['national_id']

    def __str__(self):
        return f"Patient {self.national_id}"


class HealthVisit(models.Model):
    """
    Consultation ou hospitalisation — APPEND-ONLY.

    Jamais de DELETE ni de UPDATE après création.
    Chaque visite est un fait médical inscrit dans le temps.
    """

    class TypeVisite(models.TextChoices):
        CONSULTATION    = 'CONSULTATION',    'Consultation'
        HOSPITALISATION = 'HOSPITALISATION', 'Hospitalisation'
        URGENCE         = 'URGENCE',         'Urgence'
        TELECONSULTATION = 'TELECONSULTATION', 'Téléconsultation'

    patient  = models.ForeignKey(HealthPatient, on_delete=models.CASCADE, related_name='visits')
    facility = models.ForeignKey(SectorTenant,  on_delete=models.CASCADE, related_name='health_visits')
    agent    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name='health_visits',
    )

    type_visite = models.CharField(max_length=20, choices=TypeVisite.choices,
                                   default=TypeVisite.CONSULTATION)

    # Motif de la visite (obligatoire)
    motif = models.CharField(max_length=300)

    # Diagnostic ICD-10 (optionnel à la création, renseigné après examen)
    diagnostic_code    = models.CharField(max_length=10, blank=True)
    diagnostic_libelle = models.CharField(max_length=200, blank=True)

    date_visite = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "visite médicale"
        ordering = ['-date_visite']
        indexes = [
            models.Index(fields=['patient', 'date_visite']),
            models.Index(fields=['facility', 'date_visite']),
        ]

    def __str__(self):
        return f"[{self.type_visite}] {self.patient.national_id} @ {self.facility.name}"


class HealthVaccination(models.Model):
    """
    Vaccination enregistrée dans le carnet vaccinal numérique — APPEND-ONLY.

    `vaccin_code` suit le standard PEV-RDC (BCG, PENTA, RR, OPV…).
    `dose_numero` permet de tracer les doses multiples (ex. PENTA1, PENTA2, PENTA3).
    """

    patient       = models.ForeignKey(HealthPatient, on_delete=models.CASCADE,
                                      related_name='vaccinations')
    facility      = models.ForeignKey(SectorTenant, on_delete=models.CASCADE,
                                      related_name='health_vaccinations')
    agent         = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name='health_vaccinations',
    )

    vaccin_nom    = models.CharField(max_length=120)
    vaccin_code   = models.CharField(max_length=20)  # ex. BCG, PENTA, RR, OPV, VPO
    dose_numero   = models.PositiveSmallIntegerField(default=1)
    date_administration = models.DateField()

    # Numéro de lot pour la traçabilité pharmacovigilance
    lot_numero    = models.CharField(max_length=60, blank=True)

    class Meta:
        verbose_name = "vaccination"
        ordering = ['-date_administration']
        indexes = [
            models.Index(fields=['patient', 'vaccin_code']),
        ]

    def __str__(self):
        return f"{self.vaccin_code} dose {self.dose_numero} — {self.patient.national_id}"


class HealthPrescription(models.Model):
    """
    Ordonnance médicale — APPEND-ONLY.

    Liée optionnellement à une visite (`visit`).
    `est_delivre` est le seul champ modifiable (marqué True quand la pharmacie délivre).
    Toutes les autres valeurs sont immuables après création.
    """

    patient  = models.ForeignKey(HealthPatient, on_delete=models.CASCADE,
                                 related_name='prescriptions')

    # Visite associée (nullable : ordonnance de renouvellement sans nouvelle visite)
    visit    = models.ForeignKey(HealthVisit, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='prescriptions')

    prescrit_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name='health_prescriptions',
    )
    facility = models.ForeignKey(SectorTenant, on_delete=models.CASCADE,
                                 related_name='health_prescriptions')

    medicament_nom   = models.CharField(max_length=150)
    posologie        = models.CharField(max_length=200,
                                        help_text="Ex. : 2 comprimés × 3/jour pendant 7 jours.")
    date_prescription = models.DateField(auto_now_add=True)

    # Seul champ mutable : True quand la pharmacie a délivré le médicament
    est_delivre = models.BooleanField(default=False)

    class Meta:
        verbose_name = "prescription"
        ordering = ['-date_prescription']

    def __str__(self):
        return f"{self.medicament_nom} → {self.patient.national_id}"


class EpidemioAlert(models.Model):
    """
    Alerte épidémiologique — données mock v1.

    Modélise une flambée de maladie dans une province / territoire.
    `taux_letalite` est calculé à la volée (property).

    Intégration réelle prévue : DHIS2 (standard OMS/Ministère Santé RDC)
    via une commande `sync_dhis2` similaire à `sync_siga`.
    Pour v1 : données insérées via le shell ou des fixtures de seed.
    """

    class Niveau(models.TextChoices):
        FAIBLE   = 'FAIBLE',   'Faible'
        MODERE   = 'MODERE',   'Modéré'
        ELEVE    = 'ELEVE',    'Élevé'
        CRITIQUE = 'CRITIQUE', 'Critique'

    class Statut(models.TextChoices):
        EN_COURS  = 'EN_COURS',  'En cours'
        SURVEILLE = 'SURVEILLE', 'Sous surveillance'
        RESOLU    = 'RESOLU',    'Résolu'

    disease_code = models.CharField(max_length=20,
                                    help_text="Code ICD-10 ou code local (ex. CHOLERA-01).")
    disease_name = models.CharField(max_length=150)

    # Localisation géographique
    province     = models.CharField(max_length=100)
    territoire   = models.CharField(max_length=100, blank=True)

    # Compteurs épidémiologiques
    cas_confirmes = models.PositiveIntegerField(default=0)
    cas_suspects  = models.PositiveIntegerField(default=0)
    deces         = models.PositiveIntegerField(default=0)

    date_debut = models.DateField()
    date_fin   = models.DateField(null=True, blank=True)

    niveau = models.CharField(max_length=10, choices=Niveau.choices, default=Niveau.MODERE)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_COURS)

    # Source de l'information (OMS, Ministère Santé, CDC…)
    source = models.CharField(max_length=100, blank=True)

    @property
    def taux_letalite(self) -> float:
        """Taux de létalité = décès / cas confirmés × 100. 0.0 si aucun cas."""
        if not self.cas_confirmes:
            return 0.0
        return round(self.deces / self.cas_confirmes * 100, 2)

    class Meta:
        verbose_name = "alerte épidémiologique"
        ordering = ['-date_debut']
        indexes = [
            models.Index(fields=['statut', 'date_debut']),
            models.Index(fields=['province', 'statut']),
        ]

    def __str__(self):
        return f"[{self.niveau}] {self.disease_name} — {self.province} ({self.statut})"
