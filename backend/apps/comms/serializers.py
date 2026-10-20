"""
Serializers Module 06 — Eyeshield Comms.
"""
from rest_framework import serializers

from .models import CallRecord, CommsAlert, SimCard


class SimCardSerializer(serializers.ModelSerializer):
    registered_by_username = serializers.CharField(
        source='registered_by.username', read_only=True, default=None
    )

    class Meta:
        model  = SimCard
        fields = [
            'id', 'msisdn', 'imei', 'national_id', 'operator', 'status',
            'registered_by', 'registered_by_username', 'registered_at', 'last_seen_at',
        ]
        read_only_fields = ['id', 'registered_by', 'registered_by_username', 'registered_at']


class SimCardCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SimCard
        fields = ['msisdn', 'imei', 'national_id', 'operator', 'status']


class CallRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CallRecord
        fields = [
            'id', 'caller_msisdn', 'callee_msisdn', 'call_type',
            'duration_sec', 'started_at', 'cell_tower_id', 'province', 'caller_imei',
        ]
        # Les CDR sont APPEND-ONLY — on expose tout en lecture seule après création
        read_only_fields = ['id']


class CommsAlertSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True, default=None
    )

    class Meta:
        model  = CommsAlert
        fields = [
            'id', 'alert_type', 'severity', 'national_id',
            'msisdn_a', 'msisdn_b', 'title', 'description',
            'status', 'evidence', 'created_by', 'created_by_username',
            'created_at', 'resolved_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_by_username', 'created_at']


class CommsAlertCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CommsAlert
        fields = [
            'alert_type', 'severity', 'national_id',
            'msisdn_a', 'msisdn_b', 'title', 'description', 'evidence',
        ]
