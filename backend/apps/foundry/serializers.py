"""Serializers Module 03 — Eyeshield Foundry."""
from rest_framework import serializers

from .models import SectorTenant, FraudAlert, KYCRecord


class SectorTenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = SectorTenant
        fields = ['id', 'name', 'sector', 'is_active', 'created_at']


class FraudAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudAlert
        fields = [
            'id', 'national_id', 'severity', 'tenant_count',
            'tenant_names', 'window_minutes', 'detected_at', 'is_resolved',
        ]


class KYCRecordSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)

    class Meta:
        model = KYCRecord
        fields = ['id', 'national_id', 'tenant_name', 'status', 'created_at']
