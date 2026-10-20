"""
Vues Module 04 — Eyeshield Intel.

GET  /api/v4/intel/alerts/                      → liste alertes (filtres type, severity, status)
POST /api/v4/intel/alerts/                      → créer alerte manuelle
GET  /api/v4/intel/alerts/<id>/                 → détail + preuves
PATCH /api/v4/intel/alerts/<id>/status/         → changer le statut
GET  /api/v4/intel/network/<national_id>/       → graphe réseau d'un citoyen
POST /api/v4/intel/network/links/               → ajouter un lien réseau (upsert)
GET  /api/v4/intel/threats/                     → zones de menace actives
POST /api/v4/intel/threats/                     → déclarer une zone de menace
GET  /api/v4/intel/stats/                       → dashboard agrégé (admin/intel)
"""
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.intel.models import IntelAlert, NetworkLink, ThreatZone
from apps.intel.permissions import IsIntelAnalyst, IsIntelReader
from apps.intel.serializers import (
    IntelAlertCreateSerializer,
    IntelAlertDetailSerializer,
    IntelAlertListSerializer,
    IntelAlertStatusUpdateSerializer,
    IntelStatsSerializer,
    NetworkGraphSerializer,
    NetworkLinkCreateSerializer,
    NetworkLinkSerializer,
    ThreatZoneSerializer,
)


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


# ── Alertes ───────────────────────────────────────────────────────────────────

class IntelAlertListCreateView(APIView):
    """
    GET  /api/v4/intel/alerts/  — liste paginée (filtres : type, severity, status, national_id)
    POST /api/v4/intel/alerts/  — créer une alerte manuelle (ROLE_INTEL / ADMIN)
    """
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsIntelAnalyst()]
        return [IsIntelReader()]

    def get(self, request):
        qs = IntelAlert.objects.select_related('assigned_to', 'created_by')

        alert_type = request.query_params.get('type', '').strip().upper()
        if alert_type:
            qs = qs.filter(alert_type=alert_type)

        severity = request.query_params.get('severity', '').strip().upper()
        if severity:
            qs = qs.filter(severity=severity)

        status_filter = request.query_params.get('status', '').strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)

        national_id = request.query_params.get('national_id', '').strip()
        if national_id:
            qs = qs.filter(national_id=national_id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = IntelAlertListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = IntelAlertCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        alert = serializer.save()
        return Response(
            IntelAlertDetailSerializer(alert).data,
            status=http_status.HTTP_201_CREATED,
        )


class IntelAlertDetailView(APIView):
    """
    GET /api/v4/intel/alerts/<pk>/  — détail complet avec preuves brutes.
    """
    permission_classes = [IsIntelReader]

    def get(self, request, pk: int):
        try:
            alert = IntelAlert.objects.select_related('assigned_to', 'created_by').get(pk=pk)
        except IntelAlert.DoesNotExist:
            return Response({'detail': 'Alerte introuvable.'}, status=http_status.HTTP_404_NOT_FOUND)
        return Response(IntelAlertDetailSerializer(alert).data)


class IntelAlertStatusView(APIView):
    """
    PATCH /api/v4/intel/alerts/<pk>/status/  — mettre à jour le statut.
    Enregistre resolved_at automatiquement si le nouveau statut est CLOSED ou FALSE_POSITIVE.
    """
    permission_classes = [IsIntelAnalyst]

    def patch(self, request, pk: int):
        try:
            alert = IntelAlert.objects.get(pk=pk)
        except IntelAlert.DoesNotExist:
            return Response({'detail': 'Alerte introuvable.'}, status=http_status.HTTP_404_NOT_FOUND)

        serializer = IntelAlertStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        alert.status = new_status
        # Marquer resolved_at si l'alerte est fermée
        if new_status in (IntelAlert.Status.CLOSED, IntelAlert.Status.FALSE_POSITIVE):
            alert.resolved_at = alert.resolved_at or timezone.now()
        alert.save(update_fields=['status', 'resolved_at'])

        return Response(IntelAlertDetailSerializer(alert).data)


# ── Graphe réseau ─────────────────────────────────────────────────────────────

class NetworkGraphView(APIView):
    """
    GET /api/v4/intel/network/<national_id>/

    Retourne le graphe réseau d'un citoyen :
    - nodes : le sujet + tous ses voisins directs
    - edges : tous les liens qui les relient

    Optionnel : ?min_strength=0.5 pour filtrer les liens faibles.
    """
    permission_classes = [IsIntelReader]

    def get(self, request, national_id: str):
        min_strength = float(request.query_params.get('min_strength', 0.0))

        # Tous les liens où national_id est source OU cible
        edges = list(
            NetworkLink.objects.filter(
                Q(source_national_id=national_id) | Q(target_national_id=national_id),
                strength__gte=min_strength,
            )
        )

        # Construire l'ensemble des national_ids voisins
        neighbour_ids = set()
        for edge in edges:
            neighbour_ids.add(edge.source_national_id)
            neighbour_ids.add(edge.target_national_id)
        neighbour_ids.discard(national_id)

        # Tenter de résoudre les noms via Citizen (pas obligatoire — peut ne pas exister)
        try:
            from apps.citizens.models import Citizen
            citizen_map = {
                c.national_id: f"{c.prenom} {c.nom}"
                for c in Citizen.objects.filter(
                    national_id__in=(neighbour_ids | {national_id})
                ).only('national_id', 'nom', 'prenom')
            }
        except Exception:
            citizen_map = {}

        nodes = [{'national_id': national_id, 'label': citizen_map.get(national_id, national_id), 'role': 'subject'}]
        for nid in sorted(neighbour_ids):
            nodes.append({
                'national_id': nid,
                'label': citizen_map.get(nid, nid),
                'role': 'associate',
            })

        graph = {
            'national_id': national_id,
            'nodes':       nodes,
            'edges':       edges,
            'total_nodes': len(nodes),
            'total_edges': len(edges),
        }
        serializer = NetworkGraphSerializer(graph)
        return Response(serializer.data)


class NetworkLinkCreateView(APIView):
    """
    POST /api/v4/intel/network/links/  — upsert d'un lien réseau (ROLE_INTEL / ADMIN).
    """
    permission_classes = [IsIntelAnalyst]

    def post(self, request):
        serializer = NetworkLinkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        link, _ = NetworkLink.objects.update_or_create(
            source_national_id=vd['source_national_id'],
            target_national_id=vd['target_national_id'],
            link_type=vd['link_type'],
            defaults={'strength': vd.get('strength', 1.0), 'evidence': vd.get('evidence', {})},
        )
        return Response(NetworkLinkSerializer(link).data, status=http_status.HTTP_201_CREATED)


# ── Zones de menace ───────────────────────────────────────────────────────────

class ThreatZoneListCreateView(APIView):
    """
    GET  /api/v4/intel/threats/  — liste des zones actives (filtres province, type, severity)
    POST /api/v4/intel/threats/  — déclarer une nouvelle zone (ROLE_INTEL / ADMIN)
    """
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsIntelAnalyst()]
        return [IsIntelReader()]

    def get(self, request):
        qs = ThreatZone.objects.all()

        province = request.query_params.get('province', '').strip()
        if province:
            qs = qs.filter(province__icontains=province)

        threat_type = request.query_params.get('type', '').strip().upper()
        if threat_type:
            qs = qs.filter(threat_type=threat_type)

        severity = request.query_params.get('severity', '').strip().upper()
        if severity:
            qs = qs.filter(severity=severity)

        status_filter = request.query_params.get('status', 'ACTIVE').strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ThreatZoneSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = ThreatZoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        zone = serializer.save(reported_by=request.user)
        return Response(serializer.data, status=http_status.HTTP_201_CREATED)


# ── Dashboard ─────────────────────────────────────────────────────────────────

class IntelStatsView(APIView):
    """
    GET /api/v4/intel/stats/  — dashboard agrégé (ROLE_INTEL / ADMIN).
    """
    permission_classes = [IsIntelAnalyst]

    def get(self, request):
        alerts_by_type = list(
            IntelAlert.objects.values('alert_type').annotate(count=Count('id')).order_by('-count')
        )
        alerts_by_severity = list(
            IntelAlert.objects.values('severity').annotate(count=Count('id')).order_by('-count')
        )
        threats_by_type = list(
            ThreatZone.objects.filter(status='ACTIVE')
            .values('threat_type').annotate(count=Count('id')).order_by('-count')
        )

        stats = {
            'total_alerts':        IntelAlert.objects.count(),
            'open_alerts':         IntelAlert.objects.filter(status='OPEN').count(),
            'critical_alerts':     IntelAlert.objects.filter(severity='CRITICAL').count(),
            'alerts_by_type':      [{'type': r['alert_type'], 'count': r['count']} for r in alerts_by_type],
            'alerts_by_severity':  [{'severity': r['severity'], 'count': r['count']} for r in alerts_by_severity],
            'total_network_links': NetworkLink.objects.count(),
            'total_threat_zones':  ThreatZone.objects.count(),
            'active_threat_zones': ThreatZone.objects.filter(status='ACTIVE').count(),
            'threats_by_type':     [{'type': r['threat_type'], 'count': r['count']} for r in threats_by_type],
        }
        serializer = IntelStatsSerializer(stats)
        return Response(serializer.data)
