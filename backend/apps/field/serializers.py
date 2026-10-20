"""Serializers Module 07 — Eyeshield Field."""
from rest_framework import serializers

from .models import FieldAgent, FieldMission, FieldRecord, SyncBatch


class FieldAgentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='agent.username', read_only=True)

    class Meta:
        model  = FieldAgent
        fields = [
            'id', 'agent', 'username', 'device_id',
            'zone_province', 'zone_territoire', 'status',
            'last_sync_at', 'created_at',
        ]
        read_only_fields = ['id', 'agent', 'username', 'created_at']


class FieldMissionSerializer(serializers.ModelSerializer):
    agent_username = serializers.CharField(source='agent.agent.username', read_only=True)

    class Meta:
        model  = FieldMission
        fields = [
            'id', 'agent', 'agent_username', 'title', 'description',
            'mission_type', 'province', 'territoire', 'status',
            'assigned_by', 'assigned_at', 'started_at', 'completed_at', 'due_date',
        ]
        read_only_fields = ['id', 'agent_username', 'assigned_by', 'assigned_at']


class FieldMissionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FieldMission
        fields = ['agent', 'title', 'description', 'mission_type', 'province', 'territoire', 'due_date']


class FieldRecordSerializer(serializers.ModelSerializer):
    agent_username = serializers.CharField(source='field_agent.agent.username', read_only=True)

    class Meta:
        model  = FieldRecord
        fields = [
            'id', 'mission', 'field_agent', 'agent_username',
            'record_type', 'national_id', 'description',
            'coordinates', 'province', 'territoire',
            'offline_at', 'synced_at', 'evidence',
        ]
        read_only_fields = ['id', 'agent_username', 'synced_at']


class SyncRecordInputSerializer(serializers.Serializer):
    """Un seul record dans le payload de sync."""
    record_type = serializers.ChoiceField(choices=FieldRecord.RecordType.choices)
    national_id = serializers.CharField(max_length=20, allow_blank=True, default='')
    description = serializers.CharField(allow_blank=True, default='')
    coordinates = serializers.DictField(default=dict)
    province    = serializers.CharField(max_length=100, allow_blank=True, default='')
    territoire  = serializers.CharField(max_length=100, allow_blank=True, default='')
    offline_at  = serializers.DateTimeField()
    evidence    = serializers.DictField(default=dict)
    mission_id  = serializers.IntegerField(required=False, allow_null=True, default=None)


class SyncBatchInputSerializer(serializers.Serializer):
    """Payload complet d'une synchronisation depuis un appareil."""
    device_id = serializers.CharField(max_length=64, allow_blank=True, default='')
    records   = SyncRecordInputSerializer(many=True)


class SyncBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SyncBatch
        fields = [
            'id', 'field_agent', 'device_id', 'records_count',
            'accepted_count', 'duplicate_count', 'synced_at', 'status', 'error_log',
        ]
        read_only_fields = fields
