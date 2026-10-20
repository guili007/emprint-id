"""
Vues Module 06 — Eyeshield Comms.

GET  /api/v6/comms/sims/                     → liste SIMs (filtres national_id, operator, status)
POST /api/v6/comms/sims/                     → enregistrer une SIM
GET  /api/v6/comms/sims/<national_id>/profile/ → profil télécom complet d'un citoyen
GET  /api/v6/comms/records/                  → liste CDR (filtres msisdn, date_from, date_to)
POST /api/v6/comms/records/                  → importer un CDR (APPEND-ONLY)
GET  /api/v6/comms/alerts/                   → alertes corrélation télécom
POST /api/v6/comms/alerts/                   → créer une alerte manuelle
GET  /api/v6/comms/stats/                    → statistiques agrégées
"""
import logging

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CallRecord, CommsAlert, SimCard
from .permissions import IsCommsAnalyst, IsCommsReader
from .serializers import (
    CallRecordSerializer,
    CommsAlertCreateSerializer,
    CommsAlertSerializer,
    SimCardCreateSerializer,
    SimCardSerializer,
)

logger = logging.getLogger('emprint.comms')


# ── SIMs ──────────────────────────────────────────────────────────────────────

class SimCardListCreateView(APIView):
    """
    GET  /api/v6/comms/sims/ — liste + filtres
    POST /api/v6/comms/sims/ — enregistrer une nouvelle SIM
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsCommsAnalyst()]
        return [IsCommsReader()]

    def get(self, request):
        qs = SimCard.objects.select_related('registered_by').order_by('-registered_at')

        national_id = request.query_params.get('national_id')
        if national_id:
            qs = qs.filter(national_id=national_id)

        operator = request.query_params.get('operator')
        if operator:
            qs = qs.filter(operator=operator)

        sim_status = request.query_params.get('status')
        if sim_status:
            qs = qs.filter(status=sim_status)

        imei = request.query_params.get('imei')
        if imei:
            qs = qs.filter(imei=imei)

        return Response(SimCardSerializer(qs[:200], many=True).data)

    def post(self, request):
        serializer = SimCardCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        sim = serializer.save(registered_by=request.user)
        return Response(SimCardSerializer(sim).data, status=status.HTTP_201_CREATED)


class SimCardProfileView(APIView):
    """
    GET /api/v6/comms/sims/<national_id>/profile/
    Profil télécom complet : toutes les SIMs + IMEIs connus + derniers CDR.
    """
    permission_classes = [IsCommsReader]

    def get(self, request, national_id):
        sims = SimCard.objects.filter(national_id=national_id).order_by('-registered_at')

        if not sims.exists():
            return Response(
                {'detail': 'Aucune SIM enregistrée pour cet identifiant.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # IMEIs distincts vus pour ce citoyen — indicateur multi-appareil
        imeis = list(sims.exclude(imei='').values_list('imei', flat=True).distinct())

        # Derniers CDR émis par l'un de ses MSISDN
        msisdns = list(sims.values_list('msisdn', flat=True))
        recent_records = CallRecord.objects.filter(
            caller_msisdn__in=msisdns
        ).order_by('-started_at')[:20]

        # Alertes actives liées à ce citoyen
        active_alerts = CommsAlert.objects.filter(
            national_id=national_id, status='OPEN'
        ).count()

        return Response({
            'national_id':    national_id,
            'sim_count':      sims.count(),
            'sims':           SimCardSerializer(sims, many=True).data,
            'known_imeis':    imeis,
            'recent_records': CallRecordSerializer(recent_records, many=True).data,
            'active_alerts':  active_alerts,
        })


# ── CDR ───────────────────────────────────────────────────────────────────────

class CallRecordListCreateView(APIView):
    """
    GET  /api/v6/comms/records/ — liste CDR (filtres msisdn, call_type, date)
    POST /api/v6/comms/records/ — importer un CDR (APPEND-ONLY)
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsCommsAnalyst()]
        return [IsCommsReader()]

    def get(self, request):
        qs = CallRecord.objects.order_by('-started_at')

        msisdn = request.query_params.get('msisdn')
        if msisdn:
            qs = qs.filter(Q(caller_msisdn=msisdn) | Q(callee_msisdn=msisdn))

        call_type = request.query_params.get('call_type')
        if call_type:
            qs = qs.filter(call_type=call_type)

        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(started_at__date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(started_at__date__lte=date_to)

        return Response(CallRecordSerializer(qs[:200], many=True).data)

    def post(self, request):
        serializer = CallRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        record = serializer.save()

        # Mise à jour de last_seen_at sur la SIM correspondante si elle existe
        SimCard.objects.filter(msisdn=record.caller_msisdn).update(last_seen_at=record.started_at)

        return Response(CallRecordSerializer(record).data, status=status.HTTP_201_CREATED)


# ── Alertes ───────────────────────────────────────────────────────────────────

class CommsAlertListCreateView(APIView):
    """
    GET  /api/v6/comms/alerts/ — liste + filtres
    POST /api/v6/comms/alerts/ — créer une alerte manuelle
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsCommsAnalyst()]
        return [IsCommsReader()]

    def get(self, request):
        qs = CommsAlert.objects.select_related('created_by').order_by('-created_at')

        alert_status = request.query_params.get('status')
        if alert_status:
            qs = qs.filter(status=alert_status)

        alert_type = request.query_params.get('alert_type')
        if alert_type:
            qs = qs.filter(alert_type=alert_type)

        severity = request.query_params.get('severity')
        if severity:
            qs = qs.filter(severity=severity)

        national_id = request.query_params.get('national_id')
        if national_id:
            qs = qs.filter(national_id=national_id)

        return Response(CommsAlertSerializer(qs[:200], many=True).data)

    def post(self, request):
        serializer = CommsAlertCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        alert = serializer.save(created_by=request.user)
        return Response(CommsAlertSerializer(alert).data, status=status.HTTP_201_CREATED)


# ── Stats ─────────────────────────────────────────────────────────────────────

class CommsStatsView(APIView):
    """
    GET /api/v6/comms/stats/
    Dashboard agrégé : SIMs actives, CDR du jour, alertes ouvertes.
    """
    permission_classes = [IsCommsReader]

    def get(self, request):
        today = timezone.now().date()

        sim_by_operator = dict(
            SimCard.objects.filter(status='ACTIVE')
            .values('operator')
            .annotate(c=Count('id'))
            .values_list('operator', 'c')
        )

        sim_by_status = dict(
            SimCard.objects.values('status')
            .annotate(c=Count('id'))
            .values_list('status', 'c')
        )

        alerts_by_type = dict(
            CommsAlert.objects.filter(status='OPEN')
            .values('alert_type')
            .annotate(c=Count('id'))
            .values_list('alert_type', 'c')
        )

        return Response({
            'sims': {
                'total':       SimCard.objects.count(),
                'active':      SimCard.objects.filter(status='ACTIVE').count(),
                'blacklisted': SimCard.objects.filter(status='BLACKLISTED').count(),
                'by_operator': sim_by_operator,
                'by_status':   sim_by_status,
            },
            'call_records': {
                'total': CallRecord.objects.count(),
                'today': CallRecord.objects.filter(started_at__date=today).count(),
            },
            'alerts': {
                'open':     CommsAlert.objects.filter(status='OPEN').count(),
                'critical': CommsAlert.objects.filter(status='OPEN', severity='CRITICAL').count(),
                'by_type':  alerts_by_type,
            },
        })


# ── Détection IMEI swap ───────────────────────────────────────────────────────

def severity_for_imei_swap(swap_count: int) -> str:
    """
    Détermine la sévérité d'une alerte IMEI_SWAP selon le nombre de swaps.

    Un swap = la même SIM (MSISDN) a été utilisée sur un IMEI différent.
    En pratique : 1 swap = changement d'appareil normal, 5+ = suspect.

    TODO(human): Implémente la logique de sévérité.
    Retourne une des valeurs : 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
    """
    pass  # TODO(human)
