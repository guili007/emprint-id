"""
Serializers Module 05 — Eyeshield Audit.

Quatre serializers :
  AuditEventSerializer       — trail d'audit (lecture seule côté API)
  ComplianceFlagSerializer   — flags de non-conformité
  ComplianceFlagStatusSerializer — PATCH statut uniquement
  AuditReportSerializer      — rapports de conformité (lecture + création)
"""
from rest_framework import serializers

from .models import AuditEvent, AuditReport, ComplianceFlag


class AuditEventSerializer(serializers.ModelSerializer):
    # Exposer le username de l'acteur sans inclure le mot de passe
    actor_username = serializers.CharField(source='actor.username', read_only=True, default=None)

    class Meta:
        model = AuditEvent
        fields = [
            'id', 'event_type', 'actor', 'actor_username', 'actor_role',
            'target_national_id', 'ip_address', 'details', 'created_at',
        ]
        # Tous les champs sont en lecture seule — les événements se créent via
        # le helper interne `log_audit_event()`, jamais directement via l'API
        read_only_fields = fields


class ComplianceFlagSerializer(serializers.ModelSerializer):
    actor_username     = serializers.CharField(source='actor.username', read_only=True, default=None)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True, default=None)

    class Meta:
        model = ComplianceFlag
        fields = [
            'id', 'flag_type', 'severity', 'actor', 'actor_username', 'actor_role',
            'target_national_id', 'description', 'status',
            'reviewed_by', 'reviewed_by_username', 'reviewed_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'flag_type', 'severity', 'actor', 'actor_username', 'actor_role',
            'target_national_id', 'description',
            'reviewed_by', 'reviewed_by_username', 'reviewed_at', 'created_at',
        ]


class ComplianceFlagStatusSerializer(serializers.Serializer):
    """Payload minimal pour PATCH /flags/<id>/status/."""
    status = serializers.ChoiceField(choices=ComplianceFlag.FlagStatus.choices)


class AuditReportSerializer(serializers.ModelSerializer):
    generated_by_username = serializers.CharField(
        source='generated_by.username', read_only=True, default=None
    )

    class Meta:
        model = AuditReport
        fields = [
            'id', 'report_type', 'period_start', 'period_end',
            'generated_by', 'generated_by_username',
            'generated_at', 'status', 'summary',
        ]
        # generated_by, generated_at, status, summary sont remplis par la vue
        read_only_fields = [
            'id', 'generated_by', 'generated_by_username',
            'generated_at', 'status', 'summary',
        ]
