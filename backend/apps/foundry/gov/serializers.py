"""Serializers Foundry Gov."""
from rest_framework import serializers

from apps.foundry.models import GovEmployee, GovCareerEvent, GovBudgetLine, GovContract


class GovCareerEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = GovCareerEvent
        fields = [
            'type_evenement', 'date_effet',
            'grade_code', 'unite_nom', 'reference_acte',
        ]


class GovEmployeeSerializer(serializers.ModelSerializer):
    """Sérialiseur liste — sans les événements de carrière (trop lourd)."""

    class Meta:
        model = GovEmployee
        fields = [
            'siga_uuid', 'matricule',
            'nom', 'postnom', 'prenom', 'sexe',
            'statut', 'grade_code', 'grade_libelle',
            'unite_nom', 'unite_type', 'administration_nom',
            'has_diplome_verifie', 'synced_at',
        ]


class GovEmployeeDetailSerializer(GovEmployeeSerializer):
    """Sérialiseur détail — inclut les événements de carrière."""
    career_events = GovCareerEventSerializer(many=True, read_only=True)

    class Meta(GovEmployeeSerializer.Meta):
        fields = GovEmployeeSerializer.Meta.fields + ['career_events']


class GovBudgetLineSerializer(serializers.ModelSerializer):
    # Taux d'exécution calculé à la volée (property sur le modèle)
    taux_execution = serializers.FloatField(read_only=True)

    class Meta:
        model = GovBudgetLine
        fields = [
            'id', 'annee', 'ministere', 'poste_budgetaire',
            'montant_alloue', 'montant_execute', 'taux_execution',
        ]


class GovContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = GovContract
        fields = [
            'reference', 'objet',
            'fournisseur_nom', 'fournisseur_national_id',
            'montant', 'statut', 'ministere', 'date_attribution',
        ]
