"""Serializers Module 08 — Eyeshield Justice."""
from rest_framework import serializers

from .models import ArrestWarrant, CriminalRecord, JusticeAlert


class CriminalRecordSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model  = CriminalRecord
        fields = [
            'id', 'national_id', 'record_type', 'offense_code', 'offense_description',
            'judgment_date', 'court_name', 'sentence_type', 'sentence_duration_months',
            'fine_amount_cdf', 'release_date', 'created_by', 'created_by_username', 'created_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_by_username', 'created_at']


class CriminalRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CriminalRecord
        fields = [
            'national_id', 'record_type', 'offense_code', 'offense_description',
            'judgment_date', 'court_name', 'sentence_type', 'sentence_duration_months',
            'fine_amount_cdf', 'release_date',
        ]


class ArrestWarrantSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model  = ArrestWarrant
        fields = [
            'id', 'national_id', 'warrant_type', 'issued_by', 'issued_at', 'expires_at',
            'status', 'offense_description', 'created_by', 'created_by_username', 'executed_at',
        ]
        read_only_fields = ['id', 'issued_at', 'created_by', 'created_by_username']


class ArrestWarrantCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ArrestWarrant
        fields = ['national_id', 'warrant_type', 'issued_by', 'expires_at', 'offense_description']


class JusticeAlertSerializer(serializers.ModelSerializer):
    issued_by_username = serializers.CharField(source='issued_by.username', read_only=True)

    class Meta:
        model  = JusticeAlert
        fields = [
            'id', 'national_id', 'alert_type', 'severity', 'title', 'description',
            'issued_by', 'issued_by_username', 'status', 'evidence', 'created_at',
        ]
        read_only_fields = ['id', 'issued_by', 'issued_by_username', 'created_at']


class JusticeAlertCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = JusticeAlert
        fields = ['national_id', 'alert_type', 'severity', 'title', 'description', 'evidence']
