"""Sérialiseurs Module 04 — Eyeshield Intel."""
from rest_framework import serializers

from apps.intel.models import IntelAlert, NetworkLink, ThreatZone


class IntelAlertListSerializer(serializers.ModelSerializer):
    """Résumé d'alerte — pour les listes (pas les preuves brutes)."""
    assigned_to_username = serializers.CharField(
        source='assigned_to.username', read_only=True, default=None
    )

    class Meta:
        model  = IntelAlert
        fields = [
            'id', 'national_id', 'alert_type', 'severity', 'title',
            'status', 'source_module', 'assigned_to_username',
            'created_at', 'resolved_at',
        ]


class IntelAlertDetailSerializer(serializers.ModelSerializer):
    """Détail complet — inclut les preuves brutes (evidence)."""
    assigned_to_username = serializers.CharField(
        source='assigned_to.username', read_only=True, default=None
    )
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True, default=None
    )

    class Meta:
        model  = IntelAlert
        fields = [
            'id', 'national_id', 'alert_type', 'severity', 'title',
            'description', 'status', 'evidence', 'source_module',
            'assigned_to_username', 'created_by_username',
            'created_at', 'resolved_at',
        ]
        read_only_fields = ['id', 'created_at', 'assigned_to_username', 'created_by_username']


class IntelAlertCreateSerializer(serializers.ModelSerializer):
    """Serializer d'écriture pour créer une alerte manuellement."""

    class Meta:
        model  = IntelAlert
        fields = [
            'national_id', 'alert_type', 'severity', 'title',
            'description', 'evidence', 'source_module',
        ]

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        validated_data.setdefault('source_module', 'MANUAL')
        return super().create(validated_data)


class IntelAlertStatusUpdateSerializer(serializers.Serializer):
    """PATCH partiel — met à jour uniquement le statut et resolved_at."""
    status = serializers.ChoiceField(choices=IntelAlert.Status.choices)


class NetworkLinkSerializer(serializers.ModelSerializer):
    """Lien du graphe réseau — lecture."""

    class Meta:
        model  = NetworkLink
        fields = [
            'id', 'source_national_id', 'target_national_id',
            'link_type', 'strength', 'evidence', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class NetworkLinkCreateSerializer(serializers.ModelSerializer):
    """Serializer d'écriture pour ajouter un lien réseau (upsert)."""

    class Meta:
        model  = NetworkLink
        fields = ['source_national_id', 'target_national_id', 'link_type', 'strength', 'evidence']
        # Désactiver le validator unique_together : géré via update_or_create dans la vue
        validators = []

    def validate_strength(self, value):
        if not 0.0 <= value <= 1.0:
            raise serializers.ValidationError("La force doit être entre 0.0 et 1.0.")
        return value


class NetworkGraphSerializer(serializers.Serializer):
    """Graphe réseau d'un citoyen : nœuds + arêtes."""
    national_id  = serializers.CharField()
    nodes        = serializers.ListField(child=serializers.DictField())
    edges        = NetworkLinkSerializer(many=True)
    total_nodes  = serializers.IntegerField()
    total_edges  = serializers.IntegerField()


class ThreatZoneSerializer(serializers.ModelSerializer):
    """Zone de menace — lecture + écriture."""
    reported_by_username = serializers.CharField(
        source='reported_by.username', read_only=True, default=None
    )

    class Meta:
        model  = ThreatZone
        fields = [
            'id', 'name', 'province', 'territoire', 'threat_type',
            'severity', 'status', 'description', 'coordinates',
            'reported_by_username', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'reported_by_username']


class IntelStatsSerializer(serializers.Serializer):
    """Dashboard Intel — statistiques globales."""
    total_alerts          = serializers.IntegerField()
    open_alerts           = serializers.IntegerField()
    critical_alerts       = serializers.IntegerField()
    alerts_by_type        = serializers.ListField(child=serializers.DictField())
    alerts_by_severity    = serializers.ListField(child=serializers.DictField())
    total_network_links   = serializers.IntegerField()
    total_threat_zones    = serializers.IntegerField()
    active_threat_zones   = serializers.IntegerField()
    threats_by_type       = serializers.ListField(child=serializers.DictField())
