"""
Vues Module 08 — Eyeshield Justice.

GET/POST  /api/v8/justice/records/              → casier judiciaire
GET       /api/v8/justice/records/<national_id>/profile/ → profil pénal complet
GET/POST  /api/v8/justice/warrants/             → mandats judiciaires
PATCH     /api/v8/justice/warrants/<pk>/status/ → mise à jour statut mandat
GET/POST  /api/v8/justice/alerts/               → alertes judiciaires
GET       /api/v8/justice/stats/                → dashboard agrégé
"""
import logging

from django.db.models import Count
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ArrestWarrant, CriminalRecord, JusticeAlert
from .permissions import IsJusticeReader, IsJusticeWriter
from .serializers import (
    ArrestWarrantCreateSerializer,
    ArrestWarrantSerializer,
    CriminalRecordCreateSerializer,
    CriminalRecordSerializer,
    JusticeAlertCreateSerializer,
    JusticeAlertSerializer,
)

logger = logging.getLogger('emprint.justice')

# Transitions valides pour un mandat : seul ACTIVE peut changer
_VALID_WARRANT_TRANSITIONS = {
    'ACTIVE': {'EXECUTED', 'CANCELLED'},
}


class CriminalRecordListCreateView(APIView):
    """
    GET  /api/v8/justice/records/  — liste (filtres: national_id, record_type, sentence_type)
    POST /api/v8/justice/records/  — créer un record (append-only)
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsJusticeWriter()]
        return [IsJusticeReader()]

    def get(self, request):
        qs = CriminalRecord.objects.select_related('created_by').order_by('-judgment_date')

        national_id = request.query_params.get('national_id')
        if national_id:
            qs = qs.filter(national_id=national_id)

        record_type = request.query_params.get('record_type')
        if record_type:
            qs = qs.filter(record_type=record_type)

        sentence_type = request.query_params.get('sentence_type')
        if sentence_type:
            qs = qs.filter(sentence_type=sentence_type)

        return Response(CriminalRecordSerializer(qs[:200], many=True).data)

    def post(self, request):
        serializer = CriminalRecordCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        record = serializer.save(created_by=request.user)
        return Response(CriminalRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class CriminalProfileView(APIView):
    """
    GET /api/v8/justice/records/<national_id>/profile/

    Profil pénal complet d'un citoyen :
      - historique du casier
      - mandats actifs
      - alertes actives
      - score de récidive (calculé par recidivism_risk)
    """
    permission_classes = [IsJusticeReader]

    def get(self, request, national_id):
        records  = CriminalRecord.objects.filter(national_id=national_id).order_by('-judgment_date')
        warrants = ArrestWarrant.objects.filter(national_id=national_id, status='ACTIVE')
        alerts   = JusticeAlert.objects.filter(national_id=national_id, status='ACTIVE')

        risk = recidivism_risk(national_id)

        return Response({
            'national_id':      national_id,
            'records':          CriminalRecordSerializer(records, many=True).data,
            'active_warrants':  ArrestWarrantSerializer(warrants, many=True).data,
            'active_alerts':    JusticeAlertSerializer(alerts, many=True).data,
            'recidivism_risk':  risk,
        })


class ArrestWarrantListCreateView(APIView):
    """
    GET  /api/v8/justice/warrants/  — mandats (filtres: national_id, status, warrant_type)
    POST /api/v8/justice/warrants/  — émettre un mandat
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsJusticeWriter()]
        return [IsJusticeReader()]

    def get(self, request):
        qs = ArrestWarrant.objects.select_related('created_by').order_by('-issued_at')

        national_id = request.query_params.get('national_id')
        if national_id:
            qs = qs.filter(national_id=national_id)

        w_status = request.query_params.get('status')
        if w_status:
            qs = qs.filter(status=w_status)

        w_type = request.query_params.get('warrant_type')
        if w_type:
            qs = qs.filter(warrant_type=w_type)

        return Response(ArrestWarrantSerializer(qs[:100], many=True).data)

    def post(self, request):
        serializer = ArrestWarrantCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        warrant = serializer.save(created_by=request.user)
        return Response(ArrestWarrantSerializer(warrant).data, status=status.HTTP_201_CREATED)


class ArrestWarrantStatusView(APIView):
    """
    PATCH /api/v8/justice/warrants/<pk>/status/

    Transitions valides : ACTIVE → EXECUTED ou CANCELLED.
    Un mandat déjà exécuté ou annulé retourne 409.
    """
    permission_classes = [IsJusticeWriter]

    def patch(self, request, pk):
        try:
            warrant = ArrestWarrant.objects.get(pk=pk)
        except ArrestWarrant.DoesNotExist:
            return Response({'detail': 'Mandat introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        if not new_status:
            return Response({'detail': 'Champ status requis.'}, status=status.HTTP_400_BAD_REQUEST)

        allowed = _VALID_WARRANT_TRANSITIONS.get(warrant.status, set())
        if new_status not in allowed:
            return Response(
                {'detail': f"Transition invalide : {warrant.status} → {new_status}."},
                status=status.HTTP_409_CONFLICT,
            )

        warrant.status = new_status
        update_fields = ['status']
        if new_status == 'EXECUTED':
            warrant.executed_at = timezone.now()
            update_fields.append('executed_at')
        warrant.save(update_fields=update_fields)

        return Response(ArrestWarrantSerializer(warrant).data)


class JusticeAlertListCreateView(APIView):
    """
    GET  /api/v8/justice/alerts/  — alertes (filtres: national_id, alert_type, severity, status)
    POST /api/v8/justice/alerts/  — créer une alerte
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsJusticeWriter()]
        return [IsJusticeReader()]

    def get(self, request):
        qs = JusticeAlert.objects.select_related('issued_by').order_by('-created_at')

        national_id = request.query_params.get('national_id')
        if national_id:
            qs = qs.filter(national_id=national_id)

        a_type = request.query_params.get('alert_type')
        if a_type:
            qs = qs.filter(alert_type=a_type)

        severity = request.query_params.get('severity')
        if severity:
            qs = qs.filter(severity=severity)

        a_status = request.query_params.get('status')
        if a_status:
            qs = qs.filter(status=a_status)

        return Response(JusticeAlertSerializer(qs[:200], many=True).data)

    def post(self, request):
        serializer = JusticeAlertCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        alert = serializer.save(issued_by=request.user)
        return Response(JusticeAlertSerializer(alert).data, status=status.HTTP_201_CREATED)


class JusticeStatsView(APIView):
    """GET /api/v8/justice/stats/ — dashboard agrégé"""
    permission_classes = [IsJusticeReader]

    def get(self, request):
        records_by_type = dict(
            CriminalRecord.objects.values('record_type')
            .annotate(c=Count('id'))
            .values_list('record_type', 'c')
        )

        warrants_by_status = dict(
            ArrestWarrant.objects.values('status')
            .annotate(c=Count('id'))
            .values_list('status', 'c')
        )

        alerts_by_severity = dict(
            JusticeAlert.objects.filter(status='ACTIVE')
            .values('severity')
            .annotate(c=Count('id'))
            .values_list('severity', 'c')
        )

        return Response({
            'criminal_records': {
                'total':    CriminalRecord.objects.count(),
                'by_type':  records_by_type,
            },
            'warrants': {
                'total':     ArrestWarrant.objects.count(),
                'active':    ArrestWarrant.objects.filter(status='ACTIVE').count(),
                'by_status': warrants_by_status,
            },
            'alerts': {
                'total':       JusticeAlert.objects.count(),
                'active':      JusticeAlert.objects.filter(status='ACTIVE').count(),
                'by_severity': alerts_by_severity,
            },
        })


# ── Helpers internes ──────────────────────────────────────────────────────────

def recidivism_risk(national_id: str) -> dict:
    """
    Calcule un score de risque de récidive pour un citoyen.

    TODO(human): Implémente la logique de calcul du score de récidive.

    Le score doit prendre en compte :
      - Le nombre total de condamnations (FELONY, MISDEMEANOR, INFRACTION)
        → plus il y en a, plus le risque est élevé
      - Le type le plus grave : FELONY > MISDEMEANOR > INFRACTION
        → un seul FELONY suffit pour un score "HIGH"
      - Les acquittements/grâces (ACQUITTAL, PARDON) ne comptent pas

    Retourne un dict :
      {
        'score': int (0-100),
        'level': 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL',
        'conviction_count': int,
        'has_felony': bool,
      }

    Seuils suggérés pour `level` :
      0       → 'LOW'
      1-2     → 'MEDIUM'
      3-5     → 'HIGH'
      6+      → 'CRITICAL'
      mais si has_felony → minimum 'HIGH' quelle que soit la valeur

    Utilise CriminalRecord.objects.filter(...) pour compter.
    """
    pass  # TODO(human)
