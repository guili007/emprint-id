"""
Vues Module 02 — Eyeshield Data.

v2 (existant) :
  GET  /api/v2/data/citizens/search/          → recherche unifiée citoyens
  GET  /api/v2/data/stats/                    → analytics globales (ADMIN)
  GET  /api/v2/data/logs/                     → logs de vérification

v3 (ontologie) :
  GET  /api/v3/data/sources/                  → liste des sources actives
  GET  /api/v3/data/citizens/<national_id>/profile/ → profil ontologique unifié
  POST /api/v3/data/links/                    → créer/mettre à jour un lien
  GET  /api/v3/data/links/<national_id>/      → tous les liens d'un citoyen
  GET  /api/v3/data/ontology/stats/           → couverture (ADMIN)
"""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Count as DjCount
from rest_framework import status as http_status

from apps.biometric.models import VerificationLog, WatchlistEntry
from apps.citizens.models import Citizen
from apps.data.models import CitizenDataLink, DataSource
from config.signing import sign_response

from .permissions import IsAnalyticsAccess, IsDataReader
from .serializers import (
    CitizenDataLinkCreateSerializer,
    CitizenDataLinkSerializer,
    CitizenProfileSerializer,
    CitizenSearchSerializer,
    DataSourceSerializer,
    OntologyStatsSerializer,
    StatsSerializer,
    VerificationLogSerializer,
)


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class CitizenSearchView(APIView):
    """
    GET /api/v2/data/citizens/search/

    Paramètres :
      q            → national_id, nom, postnom, prenom (ILIKE)
      province     → code de province (ex. KN)
      sexe         → M | F
      is_active    → true | false
      has_watchlist → true → seulement les citoyens avec une entrée active

    La réponse watchlist est filtrée selon le rôle (voir CitizenSearchSerializer).
    """
    permission_classes = [IsDataReader]
    pagination_class = StandardPagination

    def get(self, request):
        qs = Citizen.objects.select_related('province', 'commune').prefetch_related(
            'watchlist_entries', 'face_embedding'
        )

        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(national_id__icontains=q) |
                Q(nom__icontains=q) |
                Q(postnom__icontains=q) |
                Q(prenom__icontains=q)
            )

        province = request.query_params.get('province', '').strip().upper()
        if province:
            qs = qs.filter(province__code=province)

        sexe = request.query_params.get('sexe', '').strip().upper()
        if sexe in ('M', 'F'):
            qs = qs.filter(sexe=sexe)

        is_active = request.query_params.get('is_active', '').strip().lower()
        if is_active == 'true':
            qs = qs.filter(is_active=True)
        elif is_active == 'false':
            qs = qs.filter(is_active=False)

        has_watchlist = request.query_params.get('has_watchlist', '').strip().lower()
        if has_watchlist == 'true':
            qs = qs.filter(watchlist_entries__is_active=True).distinct()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = CitizenSearchSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class LogsView(APIView):
    """
    GET /api/v2/data/logs/

    Paramètres :
      citizen_id   → national_id du citoyen
      agent        → username de l'agent
      status       → VERIFIED | REJECTED_FACE | REJECTED_LIVENESS | WATCHLIST_HIT | ERROR
      from_date    → ISO 8601
      to_date      → ISO 8601

    RBAC :
      ADMIN / WL_ADMIN → tous les logs
      Autres           → uniquement leurs propres logs
    """
    permission_classes = [IsDataReader]
    pagination_class = StandardPagination

    def get(self, request):
        role = getattr(request.user, 'role', '')
        ADMIN_ROLES = {'ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'}

        qs = VerificationLog.objects.select_related('citizen', 'agent_user').order_by('-timestamp')

        if role not in ADMIN_ROLES:
            qs = qs.filter(agent_user=request.user)

        citizen_id = request.query_params.get('citizen_id', '').strip()
        if citizen_id:
            qs = qs.filter(citizen__national_id=citizen_id)

        agent = request.query_params.get('agent', '').strip()
        if agent and role in ADMIN_ROLES:
            qs = qs.filter(agent_user__username=agent)

        status_filter = request.query_params.get('status', '').strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)

        from_date = request.query_params.get('from_date', '').strip()
        if from_date:
            qs = qs.filter(timestamp__date__gte=from_date)

        to_date = request.query_params.get('to_date', '').strip()
        if to_date:
            qs = qs.filter(timestamp__date__lte=to_date)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = VerificationLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class StatsView(APIView):
    """
    GET /api/v2/data/stats/

    Tableau de bord analytique — ADMIN / WATCHLIST_ADMIN uniquement.
    """
    permission_classes = [IsAnalyticsAccess]

    def get(self, request):
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_30d = now - timedelta(days=30)

        all_logs = VerificationLog.objects.all()
        status_counts = {
            row['status']: row['count']
            for row in all_logs.values('status').annotate(count=Count('id'))
        }

        daily_trend = list(
            VerificationLog.objects
            .filter(timestamp__gte=last_30d)
            .extra(select={'day': "DATE(timestamp)"})
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        top_provinces = list(
            VerificationLog.objects
            .filter(citizen__isnull=False)
            .values('citizen__province__nom')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        stats = {
            'total_verifications': all_logs.count(),
            'verified': status_counts.get('VERIFIED', 0),
            'rejected_face': status_counts.get('REJECTED_FACE', 0),
            'rejected_liveness': status_counts.get('REJECTED_LIVENESS', 0),
            'watchlist_hits': status_counts.get('REJECTED_WATCHLIST', 0),
            'errors': status_counts.get('ERROR', 0),
            'verif_rate_24h': all_logs.filter(timestamp__gte=last_24h).count(),
            'active_citizens': Citizen.objects.filter(is_active=True).count(),
            'active_watchlist_entries': WatchlistEntry.objects.filter(is_active=True).count(),
            'top_provinces': [
                {'province': r['citizen__province__nom'], 'count': r['count']}
                for r in top_provinces
            ],
            'daily_trend': [
                {'date': str(r['day']), 'count': r['count']}
                for r in daily_trend
            ],
        }

        serializer = StatsSerializer(stats)
        return Response(sign_response(serializer.data))


# ── Ontologie (v3) ────────────────────────────────────────────────────────────

# Mapping rôle JWT → secteurs de données autorisés (RBAC-to-sector v1)
# Les admins voient tout ; les autres ne voient que leur secteur.
_ROLE_TO_SECTORS = {
    'ROLE_BANK':            {'BANKING', 'IDENTITY'},
    'ROLE_HEALTH':          {'HEALTH', 'IDENTITY'},
    'ROLE_POLICE':          {'CIVIL', 'JUSTICE', 'IDENTITY'},
    'ROLE_BORDER':          {'JUSTICE', 'IDENTITY'},
    'ROLE_EDU':             {'EDUCATION', 'IDENTITY'},
    'ROLE_ADMIN':           None,            # None = tous les secteurs
    'ROLE_WATCHLIST_ADMIN': None,
}


def _allowed_sectors(role: str):
    """Retourne le set de secteurs autorisés pour un rôle, ou None (=tous)."""
    return _ROLE_TO_SECTORS.get(role, set())


class DataSourceListView(APIView):
    """
    GET /api/v3/data/sources/

    Liste les sources actives visibles selon le rôle de l'appelant.
    Filtre ?sector= pour n'afficher qu'un secteur.
    """
    permission_classes = [IsDataReader]

    def get(self, request):
        role    = getattr(request.user, 'role', '')
        sectors = _allowed_sectors(role)

        qs = DataSource.objects.filter(is_active=True)

        if sectors is not None:
            # Secteurs restreints selon le rôle
            qs = qs.filter(sector__in=sectors)

        sector_filter = request.query_params.get('sector', '').strip().upper()
        if sector_filter:
            qs = qs.filter(sector=sector_filter)

        serializer = DataSourceSerializer(qs, many=True)
        return Response(serializer.data)


class CitizenProfileView(APIView):
    """
    GET /api/v3/data/citizens/<national_id>/profile/

    Retourne le profil ontologique unifié d'un citoyen :
    tous ses liens vers des sources externes, filtrés selon le rôle de l'appelant.
    """
    permission_classes = [IsDataReader]

    def get(self, request, national_id: str):
        role    = getattr(request.user, 'role', '')
        sectors = _allowed_sectors(role)

        qs = CitizenDataLink.objects.select_related(
            'source', 'verified_by'
        ).filter(national_id=national_id)

        if sectors is not None:
            qs = qs.filter(source__sector__in=sectors)

        links = list(qs.order_by('source__sector', 'source__code'))

        linked_sectors = sorted({lnk.source.sector for lnk in links})
        profile = {
            'national_id':    national_id,
            'links':          links,
            'total_links':    len(links),
            'linked_sectors': linked_sectors,
        }

        serializer = CitizenProfileSerializer(profile)
        return Response(serializer.data)


class DataLinkListCreateView(APIView):
    """
    POST /api/v3/data/links/        → créer ou mettre à jour un lien (ADMIN)
    GET  /api/v3/data/links/<id>/   → tous les liens d'un citoyen (IsDataReader)
    """
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAnalyticsAccess()]
        return [IsDataReader()]

    def post(self, request):
        """Upsert d'un lien national_id ↔ source externe."""
        serializer = CitizenDataLinkCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        link = serializer.save()
        return Response(
            CitizenDataLinkSerializer(link).data,
            status=http_status.HTTP_201_CREATED,
        )


class CitizenLinksView(APIView):
    """
    GET /api/v3/data/links/<national_id>/

    Tous les liens d'un citoyen, filtrés selon le rôle.
    """
    permission_classes = [IsDataReader]
    pagination_class = StandardPagination

    def get(self, request, national_id: str):
        role    = getattr(request.user, 'role', '')
        sectors = _allowed_sectors(role)

        qs = CitizenDataLink.objects.select_related(
            'source', 'verified_by'
        ).filter(national_id=national_id)

        if sectors is not None:
            qs = qs.filter(source__sector__in=sectors)

        paginator = self.pagination_class()
        page      = paginator.paginate_queryset(qs.order_by('source__sector'), request)
        serializer = CitizenDataLinkSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class OntologyStatsView(APIView):
    """
    GET /api/v3/data/ontology/stats/

    Statistiques de couverture de la couche ontologie — ADMIN seulement.
    """
    permission_classes = [IsAnalyticsAccess]

    def get(self, request):
        total_links     = CitizenDataLink.objects.count()
        verified_links  = CitizenDataLink.objects.filter(verified_at__isnull=False).count()
        citizens_linked = CitizenDataLink.objects.values('national_id').distinct().count()

        coverage_by_sector = list(
            CitizenDataLink.objects
            .values('source__sector')
            .annotate(count=DjCount('id'))
            .order_by('-count')
        )

        top_sources = list(
            CitizenDataLink.objects
            .values('source__code', 'source__name')
            .annotate(count=DjCount('id'))
            .order_by('-count')[:10]
        )

        stats = {
            'total_sources':      DataSource.objects.count(),
            'active_sources':     DataSource.objects.filter(is_active=True).count(),
            'total_links':        total_links,
            'verified_links':     verified_links,
            'citizens_linked':    citizens_linked,
            'coverage_by_sector': [
                {'sector': r['source__sector'], 'count': r['count']}
                for r in coverage_by_sector
            ],
            'top_sources': [
                {'code': r['source__code'], 'name': r['source__name'], 'count': r['count']}
                for r in top_sources
            ],
        }

        serializer = OntologyStatsSerializer(stats)
        return Response(serializer.data)
