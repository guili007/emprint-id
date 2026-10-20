"""Serializers Foundry Edu."""
from rest_framework import serializers

from apps.foundry.models import EduSchool, EduStudent, EduBulletin, EduNoteBulletin


class EduSchoolSerializer(serializers.ModelSerializer):
    """École EduFirst — lecture seule."""

    class Meta:
        model = EduSchool
        fields = ['id', 'edufirst_school_id', 'name', 'country', 'city', 'last_synced']


class EduNoteBulletinSerializer(serializers.ModelSerializer):
    """Détail par matière dans un bulletin."""

    class Meta:
        model = EduNoteBulletin
        fields = ['matiere_nom', 'note', 'note_max', 'appreciation']


class EduBulletinSerializer(serializers.ModelSerializer):
    """Bulletin avec ses notes par matière."""
    notes = EduNoteBulletinSerializer(many=True, read_only=True)

    class Meta:
        model = EduBulletin
        fields = [
            'id', 'periode', 'annee_scolaire',
            'moyenne', 'mention', 'appreciation', 'conduite',
            'notes', 'synced_at',
        ]


class EduStudentListSerializer(serializers.ModelSerializer):
    """
    Sérialiseur liste — sans les bulletins (performances).
    Retourne uniquement les informations d'identité scolaire.
    """
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = EduStudent
        fields = [
            'id', 'edufirst_student_id', 'matricule',
            'nom', 'prenom', 'date_naissance',
            'national_id', 'school_name',
        ]


class EduStudentDetailSerializer(EduStudentListSerializer):
    """
    Sérialiseur détail — inclut les bulletins + notes par matière.
    Utilise prefetch_related pour éviter les N+1.
    """
    school   = EduSchoolSerializer(read_only=True)
    bulletins = EduBulletinSerializer(many=True, read_only=True)

    class Meta(EduStudentListSerializer.Meta):
        fields = [
            'id', 'edufirst_student_id', 'matricule',
            'nom', 'prenom', 'date_naissance',
            'national_id', 'school',
            'bulletins', 'synced_at',
        ]
