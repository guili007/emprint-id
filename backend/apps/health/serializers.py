"""
Serializers Module 09 — Eyeshield Health.
"""
from rest_framework import serializers

from .models import (
    EpidemioAlert,
    HealthPatient,
    HealthPrescription,
    HealthVaccination,
    HealthVisit,
)


# ── Patient ────────────────────────────────────────────────────────────────────

class HealthPatientListSerializer(serializers.ModelSerializer):
    """Lecture légère — sans sous-listes (évite les requêtes N+1)."""

    class Meta:
        model   = HealthPatient
        fields  = [
            'id', 'national_id', 'blood_type',
            'allergies', 'chronic_conditions',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class HealthVisitReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = HealthVisit
        fields = [
            'id', 'facility_name', 'visit_type', 'motif',
            'diagnostic_code', 'diagnostic_label', 'date_visite',
        ]


class HealthVaccinationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = HealthVaccination
        fields = [
            'id', 'vaccin_nom', 'vaccin_code', 'dose_numero',
            'date_administration', 'lot_numero', 'facility_name',
        ]


class HealthPrescriptionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = HealthPrescription
        fields = [
            'id', 'medicament_nom', 'posologie', 'facility_name',
            'date_prescription', 'est_delivre',
        ]


class HealthPatientDetailSerializer(HealthPatientListSerializer):
    """Dossier complet avec sous-listes."""
    visits        = HealthVisitReadSerializer(many=True, read_only=True)
    vaccinations  = HealthVaccinationReadSerializer(many=True, read_only=True)
    prescriptions = HealthPrescriptionReadSerializer(many=True, read_only=True)

    class Meta(HealthPatientListSerializer.Meta):
        fields = HealthPatientListSerializer.Meta.fields + [
            'visits', 'vaccinations', 'prescriptions',
        ]


class HealthPatientCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = HealthPatient
        fields = ['national_id', 'blood_type', 'allergies', 'chronic_conditions']


# ── Visite ─────────────────────────────────────────────────────────────────────

class HealthVisitCreateSerializer(serializers.ModelSerializer):
    """
    Crée une visite.  Si le dossier n'existe pas encore, il est créé automatiquement.
    national_id est passé en entrée ; le FK patient est résolu côté vue.
    """
    national_id = serializers.CharField(max_length=20, write_only=True)

    class Meta:
        model  = HealthVisit
        fields = [
            'national_id',
            'facility_name', 'visit_type', 'motif',
            'diagnostic_code', 'diagnostic_label',
        ]

    def validate_visit_type(self, value):
        valid = {c[0] for c in HealthVisit.VisitType.choices}
        if value not in valid:
            raise serializers.ValidationError(
                f"Type de visite invalide. Valeurs acceptées : {', '.join(valid)}"
            )
        return value


class HealthVisitSerializer(serializers.ModelSerializer):
    national_id = serializers.CharField(source='patient.national_id', read_only=True)

    class Meta:
        model  = HealthVisit
        fields = [
            'id', 'national_id', 'facility_name', 'visit_type',
            'motif', 'diagnostic_code', 'diagnostic_label', 'date_visite',
        ]


# ── Vaccination ────────────────────────────────────────────────────────────────

class HealthVaccinationCreateSerializer(serializers.ModelSerializer):
    national_id = serializers.CharField(max_length=20, write_only=True)

    class Meta:
        model  = HealthVaccination
        fields = [
            'national_id',
            'vaccin_nom', 'vaccin_code', 'dose_numero',
            'date_administration', 'lot_numero', 'facility_name',
        ]


class HealthVaccinationSerializer(serializers.ModelSerializer):
    national_id = serializers.CharField(source='patient.national_id', read_only=True)

    class Meta:
        model  = HealthVaccination
        fields = [
            'id', 'national_id', 'vaccin_nom', 'vaccin_code', 'dose_numero',
            'date_administration', 'lot_numero', 'facility_name',
        ]


# ── Prescription ───────────────────────────────────────────────────────────────

class HealthPrescriptionCreateSerializer(serializers.ModelSerializer):
    national_id = serializers.CharField(max_length=20, write_only=True)

    class Meta:
        model  = HealthPrescription
        fields = [
            'national_id',
            'medicament_nom', 'posologie', 'facility_name', 'est_delivre',
        ]


class HealthPrescriptionSerializer(serializers.ModelSerializer):
    national_id = serializers.CharField(source='patient.national_id', read_only=True)

    class Meta:
        model  = HealthPrescription
        fields = [
            'id', 'national_id', 'medicament_nom', 'posologie',
            'facility_name', 'date_prescription', 'est_delivre',
        ]


# ── Épidémio ───────────────────────────────────────────────────────────────────

class EpidemioAlertSerializer(serializers.ModelSerializer):
    taux_letalite = serializers.FloatField(read_only=True)

    class Meta:
        model  = EpidemioAlert
        fields = [
            'id', 'disease_code', 'disease_name',
            'province', 'territoire',
            'cas_confirmes', 'cas_suspects', 'deces',
            'date_debut', 'date_fin',
            'niveau', 'statut', 'source',
            'taux_letalite', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'taux_letalite']


class EpidemioAlertCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EpidemioAlert
        fields = [
            'disease_code', 'disease_name',
            'province', 'territoire',
            'cas_confirmes', 'cas_suspects', 'deces',
            'date_debut', 'date_fin',
            'niveau', 'statut', 'source',
        ]
