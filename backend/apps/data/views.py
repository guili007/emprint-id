"""
Vues Module 02 — Eyeshield Data.

GET /api/v2/data/citizens/search/  → recherche unifiée citoyens
GET /api/v2/data/stats/            → analytics globales (ADMIN seulement)
GET /api/v2/data/logs/             → logs de vérification (filtrés par rôle)
"""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.biometric.models import VerificationLog, WatchlistEntry
from apps.citizens.models import Citizen
from config.signing import sign_response

from .permissions import IsAnalyticsAccess, IsDataReader
from .serializers import CitizenSearchSerializer, StatsSerializer, VerificationLogSerializer


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
