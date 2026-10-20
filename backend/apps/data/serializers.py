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
