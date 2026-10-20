"""Sérialiseurs Module 02 — Eyeshield Data."""
from rest_framework import serializers

from apps.citizens.models import Citizen
from apps.biometric.models import CitizenFaceEmbedding, WatchlistEntry, VerificationLog


class CitizenSearchSerializer(serializers.ModelSerializer):
    """Profil citoyen unifié — watchlist filtrée selon le rôle de l'appelant."""
    province_nom = serializers.CharField(source='province.nom', read_only=True, default=None)
    commune_nom = serializers.CharField(source='commune.nom', read_only=True, default=None)
    has_embedding = serializers.SerializerMethodField()
    watchlist = serializers.SerializerMethodField()

    class Meta:
        model = Citizen
        fields = [
            'id', 'national_id', 'nom', 'postnom', 'prenom',
            'sexe', 'date_naissance', 'province_nom', 'commune_nom',
            'issued_at', 'is_active', 'has_embedding', 'watchlist',
        ]

    def get_has_embedding(self, obj):
        return hasattr(obj, 'face_embedding')

    def get_watchlist(self, obj):
        """
        Retourne les entrées watchlist visibles selon le rôle :
          BANK / HEALTH → toujours None (Silent Flagging Protocol)
          POLICE        → entrées CIVIL + ETAT uniquement
          BORDER        → entrées MILITAIRE + ETAT uniquement
          ADMIN / WL_ADMIN → tout
        """
        request = self.context.get('request')
        if not request:
            return None
        role = getattr(request.user, 'role', '')

        HIDDEN = {'ROLE_BANK', 'ROLE_HEALTH'}
        if role in HIDDEN:
            return None

        qs = obj.watchlist_entries.filter(is_active=True)

        if role == 'ROLE_POLICE':
            qs = qs.filter(authority__in=['CIVIL', 'ETAT'])
        elif role == 'ROLE_BORDER':
            qs = qs.filter(authority__in=['MILITAIRE', 'ETAT'])
        # ADMIN / WL_ADMIN voient tout

        entries = qs.order_by('alert_level').values(
            'alert_level', 'authority', 'issued_by', 'reason', 'issued_at'
        )
        return list(entries) if entries.exists() else []


class VerificationLogSerializer(serializers.ModelSerializer):
    citizen_id = serializers.CharField(source='citizen.national_id', read_only=True, default=None)
    agent_username = serializers.CharField(source='agent_user.username', read_only=True)

    class Meta:
        model = VerificationLog
        fields = [
            'id', 'citizen_id', 'agent_username', 'agent_role',
            'status', 'confidence_score', 'liveness_score', 'timestamp',
        ]


class StatsSerializer(serializers.Serializer):
    """Statistiques globales pour le tableau de bord analytique."""
    total_verifications = serializers.IntegerField()
    verified = serializers.IntegerField()
    rejected_face = serializers.IntegerField()
    rejected_liveness = serializers.IntegerField()
    watchlist_hits = serializers.IntegerField()
    errors = serializers.IntegerField()
    verif_rate_24h = serializers.IntegerField()
    active_citizens = serializers.IntegerField()
    active_watchlist_entries = serializers.IntegerField()
    top_provinces = serializers.ListField(child=serializers.DictField())
    daily_trend = serializers.ListField(child=serializers.DictField())


# ── Ontologie (Module 02 v2) ──────────────────────────────────────────────────

from apps.data.models import DataSource, CitizenDataLink, DataAccessPolicy  # noqa: E402


class DataSourceSerializer(serializers.ModelSerializer):
    """Source de données externe — lecture seule pour les agents accrédités."""
    sector_label = serializers.CharField(source='get_sector_display', read_only=True)

    class Meta:
        model  = DataSource
        fields = ['id', 'code', 'name', 'sector', 'sector_label', 'description', 'api_url', 'is_active']


class CitizenDataLinkSerializer(serializers.ModelSerializer):
    """Lien ontologie national_id ↔ source externe — lecture + création."""
    source_code   = serializers.CharField(source='source.code', read_only=True)
    source_sector = serializers.CharField(source='source.sector', read_only=True)
    verified_by_username = serializers.CharField(
        source='verified_by.username', read_only=True, default=None
    )

    class Meta:
        model  = CitizenDataLink
        fields = [
            'id', 'national_id', 'source', 'source_code', 'source_sector',
            'external_id', 'label', 'verified_at', 'verified_by_username',
            'metadata', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'source_code', 'source_sector', 'verified_by_username']


class CitizenDataLinkCreateSerializer(serializers.ModelSerializer):
    """Serializer d'écriture pour créer ou mettre à jour un lien ontologie."""

    class Meta:
        model  = CitizenDataLink
        fields = ['national_id', 'source', 'external_id', 'label', 'verified_at', 'metadata']
        # Désactiver les validators unique_together auto-générés par DRF :
        # la contrainte est gérée dans create() via update_or_create (upsert).
        validators = []

    def create(self, validated_data):
        # Upsert : si le lien existe déjà pour ce (national_id, source), on le met à jour
        link, _ = CitizenDataLink.objects.update_or_create(
            national_id=validated_data['national_id'],
            source=validated_data['source'],
            defaults={
                'external_id': validated_data.get('external_id', ''),
                'label':       validated_data.get('label', ''),
                'verified_at': validated_data.get('verified_at'),
                'metadata':    validated_data.get('metadata', {}),
                'verified_by': self.context['request'].user,
            },
        )
        return link


class CitizenProfileSerializer(serializers.Serializer):
    """Profil unifié d'un citoyen : tous ses liens vers les sources autorisées."""
    national_id  = serializers.CharField()
    links        = CitizenDataLinkSerializer(many=True)
    total_links  = serializers.IntegerField()
    linked_sectors = serializers.ListField(child=serializers.CharField())


class OntologyStatsSerializer(serializers.Serializer):
    """Statistiques globales de la couche ontologie — admin uniquement."""
    total_sources       = serializers.IntegerField()
    active_sources      = serializers.IntegerField()
    total_links         = serializers.IntegerField()
    verified_links      = serializers.IntegerField()
    citizens_linked     = serializers.IntegerField()
    coverage_by_sector  = serializers.ListField(child=serializers.DictField())
    top_sources         = serializers.ListField(child=serializers.DictField())
