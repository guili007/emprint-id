"""Serializers Module 10 — Eyeshield Education."""
from rest_framework import serializers

from .models import AcademicResult, Diploma, SchoolAlert, StudentRecord


# ── StudentRecord ──────────────────────────────────────────────────────────────

class AcademicResultReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AcademicResult
        fields = ['id', 'matiere', 'note', 'note_max', 'mention', 'created_at']


class StudentRecordListSerializer(serializers.ModelSerializer):
    class Meta:
        model  = StudentRecord
        fields = [
            'id', 'national_id', 'school_year', 'niveau',
            'classe', 'etablissement', 'province', 'statut',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StudentRecordDetailSerializer(StudentRecordListSerializer):
    results = AcademicResultReadSerializer(many=True, read_only=True)

    class Meta(StudentRecordListSerializer.Meta):
        fields = StudentRecordListSerializer.Meta.fields + ['results']


class StudentRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = StudentRecord
        fields = ['national_id', 'school_year', 'niveau', 'classe', 'etablissement', 'province']


# ── AcademicResult ─────────────────────────────────────────────────────────────

class AcademicResultCreateSerializer(serializers.ModelSerializer):
    """Requiert student_id (PK de StudentRecord)."""
    class Meta:
        model  = AcademicResult
        fields = ['student', 'matiere', 'note', 'note_max', 'mention']


class AcademicResultSerializer(serializers.ModelSerializer):
    national_id = serializers.CharField(source='student.national_id', read_only=True)
    school_year = serializers.CharField(source='student.school_year', read_only=True)

    class Meta:
        model  = AcademicResult
        fields = ['id', 'national_id', 'school_year', 'matiere', 'note', 'note_max', 'mention', 'created_at']


# ── Diploma ────────────────────────────────────────────────────────────────────

class DiplomaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Diploma
        fields = [
            'id', 'national_id', 'type_diplome', 'etablissement',
            'province', 'annee_obtention', 'numero_certificat',
            'mention', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class DiplomaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Diploma
        fields = [
            'national_id', 'type_diplome', 'etablissement',
            'province', 'annee_obtention', 'numero_certificat', 'mention',
        ]


# ── SchoolAlert ────────────────────────────────────────────────────────────────

class SchoolAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SchoolAlert
        fields = [
            'id', 'national_id', 'alert_type', 'severity',
            'description', 'statut', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class SchoolAlertCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SchoolAlert
        fields = ['national_id', 'alert_type', 'severity', 'description']
