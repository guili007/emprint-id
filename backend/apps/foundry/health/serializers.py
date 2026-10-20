"""Serializers Foundry Health."""
from rest_framework import serializers

from apps.foundry.models import (
    HealthPatient, HealthVisit, HealthVaccination,
    HealthPrescription, EpidemioAlert,
)


class HealthVisitSerializer(serializers.ModelSerializer):
    """
    Lecture des visites (nested dans le détail patient).
    En écriture (POST /visits/), on attend `patient_national_id`.
    """

    class Meta:
        model = HealthVisit
        fields = [
            'id', 'type_visite', 'motif',
            'diagnostic_code', 'diagnostic_libelle',
            'date_visite',
        ]


class HealthVaccinationSerializer(serializers.ModelSerializer):
    """Carnet vaccinal — nested dans le détail patient."""

    class Meta:
        model = HealthVaccination
        fields = [
            'id', 'vaccin_nom', 'vaccin_code', 'dose_numero',
            'date_administration', 'lot_numero',
        ]


class HealthPrescriptionSerializer(serializers.ModelSerializer):
    """Ordonnances — nested dans le détail patient."""

    class Meta:
        model = HealthPrescription
        fields = [
            'id', 'medicament_nom', 'posologie',
            'date_prescription', 'est_delivre',
        ]


class HealthPatientListSerializer(serializers.ModelSerializer):
    """
    Sérialiseur liste — sans les sous-listes (performances).
    Retourne uniquement les informations de base du dossier.
    """

    class Meta:
        model = HealthPatient
        fields = [
            'national_id', 'blood_type',
            'allergies', 'chronic_conditions',
            'created_at',
        ]


class HealthPatientDetailSerializer(HealthPatientListSerializer):
    """
    Sérialiseur détail — inclut les visites, vaccinations et prescriptions.
    Utilise prefetch_related pour éviter le N+1.
    """
    visits        = HealthVisitSerializer(many=True, read_only=True)
    vaccinations  = HealthVaccinationSerializer(many=True, read_only=True)
    prescriptions = HealthPrescriptionSerializer(many=True, read_only=True)

    class Meta(HealthPatientListSerializer.Meta):
        fields = HealthPatientListSerializer.Meta.fields + [
            'visits', 'vaccinations', 'prescriptions',
        ]


class HealthVisitCreateSerializer(serializers.Serializer):
    """
    Sérialiseur d'entrée pour POST /health/visits/.

    `patient_national_id` : ID national EmPrint-iD du patient.
    Le dossier patient est créé automatiquement s'il n'existe pas encore.
    """
    patient_national_id = serializers.CharField(max_length=20)
    facility_id         = serializers.UUIDField()
    type_visite         = serializers.ChoiceField(choices=HealthVisit.TypeVisite.choices,
                                                  default=HealthVisit.TypeVisite.CONSULTATION)
    motif               = serializers.CharField(max_length=300)
    diagnostic_code     = serializers.CharField(max_length=10, required=False, default='')
    diagnostic_libelle  = serializers.CharField(max_length=200, required=False, default='')


class HealthVaccinationCreateSerializer(serializers.Serializer):
    """
    Sérialiseur d'entrée pour POST /health/vaccinations/.

    Le patient doit exister (son dossier a été créé via une visite).
    """
    patient_national_id  = serializers.CharField(max_length=20)
    facility_id          = serializers.UUIDField()
    vaccin_nom           = serializers.CharField(max_length=120)
    vaccin_code          = serializers.CharField(max_length=20)
    dose_numero          = serializers.IntegerField(min_value=1, default=1)
    date_administration  = serializers.DateField()
    lot_numero           = serializers.CharField(max_length=60, required=False, default='')


class EpidemioAlertSerializer(serializers.ModelSerializer):
    """
    Alertes épidémiologiques — données mock v1.
    `taux_letalite` est une property calculée à la volée (décès / cas confirmés × 100).
    """
    # Property calculée sur le modèle, exposée en lecture seule
    taux_letalite = serializers.FloatField(read_only=True)

    class Meta:
        model = EpidemioAlert
        fields = [
            'id', 'disease_code', 'disease_name',
            'province', 'territoire',
            'cas_confirmes', 'cas_suspects', 'deces', 'taux_letalite',
            'date_debut', 'date_fin',
            'niveau', 'statut', 'source',
        ]
