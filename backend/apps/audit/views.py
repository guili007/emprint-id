"""
Views Module 05 — Eyeshield Audit.

Six endpoints :
  AuditEventListView          GET  /api/v5/audit/events/
  AuditStatsView              GET  /api/v5/audit/stats/
  ComplianceFlagListView      GET  /api/v5/audit/flags/
  ComplianceFlagStatusView    PATCH /api/v5/audit/flags/<pk>/status/
  AuditReportListCreateView   GET + POST /api/v5/audit/reports/
  AuditReportDetailView       GET  /api/v5/audit/reports/<pk>/
"""
import logging
from datetime import date

from django.db.models import Count
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditEvent, AuditReport, ComplianceFlag
from .permissions import IsAuditAdmin, IsAuditReader
from .serializers import (
    AuditEventSerializer,
    AuditReportSerializer,
    ComplianceFlagSerializer,
    ComplianceFlagStatusSerializer,
)

logger = logging.getLogger('emprint.audit')


class AuditEventListView(APIView):
    """
    GET /api/v5/audit/events/
    Paramètres : ?event_type=LOGIN &date_from=YYYY-MM-DD &date_to=YYYY-MM-DD
                 &actor_role=ROLE_ADMIN &national_id=CD-xxx
    """
    permission_classes = [IsAuditReader]

    def get(self, request):
        qs = AuditEvent.objects.select_related('actor').order_by('-created_at')

        event_type = request.query_params.get('event_type')
        if event_type:
            qs = qs.filter(event_type=event_type)

        actor_role = request.query_params.get('actor_role')
        if actor_role:
            qs = qs.filter(actor_role=actor_role)

        national_id = request.query_params.get('national_id')
        if national_id:
            qs = qs.filter(target_national_id=national_id)

        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        # Pagination manuelle légère — max 200 résultats
        qs = qs[:200]
        return Response(AuditEventSerializer(qs, many=True).data)


class AuditStatsView(APIView):
    """
    GET /api/v5/audit/stats/
    Agrège VerificationLog + IntelAlert + ComplianceFlag en un seul tableau.
    """
    permission_classes = [IsAuditReader]

    def get(self, request):
        from apps.biometric.models import VerificationLog
        from apps.intel.models import IntelAlert

        today = timezone.now().date()

        # Vérifications biométriques
        verif_total = VerificationLog.objects.count()
        verif_today = VerificationLog.objects.filter(timestamp__date=today).count()
        verif_by_status = dict(
            VerificationLog.objects.values('status')
            .annotate(c=Count('id'))
            .values_list('status', 'c')
        )

        # Alertes Intel ouvertes
        intel_open     = IntelAlert.objects.filter(status='OPEN').count()
        intel_critical = IntelAlert.objects.filter(
            status='OPEN', severity='CRITICAL'
        ).count()

        # Flags conformité ouverts
        flags_open   = ComplianceFlag.objects.filter(status='OPEN').count()
        flags_by_type = dict(
            ComplianceFlag.objects.filter(status='OPEN')
            .values('flag_type')
            .annotate(c=Count('id'))
            .values_list('flag_type', 'c')
        )

        # Événements audit aujourd'hui
        events_today = AuditEvent.objects.filter(created_at__date=today).count()

        return Response({
            'verifications': {
                'total':      verif_total,
                'today':      verif_today,
                'by_status':  verif_by_status,
            },
            'intel_alerts': {
                'open':     intel_open,
                'critical': intel_critical,
            },
            'compliance_flags': {
                'open':    flags_open,
                'by_type': flags_by_type,
            },
            'audit_events_today': events_today,
        })


class ComplianceFlagListView(APIView):
    """
    GET /api/v5/audit/flags/
    Paramètres : ?status=OPEN &flag_type=HIGH_FREQUENCY &severity=HIGH
    """
    permission_classes = [IsAuditReader]

    def get(self, request):
        qs = ComplianceFlag.objects.select_related('actor', 'reviewed_by').order_by('-created_at')

        flag_status = request.query_params.get('status')
        if flag_status:
            qs = qs.filter(status=flag_status)

        flag_type = request.query_params.get('flag_type')
        if flag_type:
            qs = qs.filter(flag_type=flag_type)

        severity = request.query_params.get('severity')
        if severity:
            qs = qs.filter(severity=severity)

        qs = qs[:200]
        return Response(ComplianceFlagSerializer(qs, many=True).data)


class ComplianceFlagStatusView(APIView):
    """
    PATCH /api/v5/audit/flags/<pk>/status/
    Autorisé : REVIEWED ou DISMISSED seulement (jamais DELETE).
    """
    permission_classes = [IsAuditAdmin]

    def patch(self, request, pk):
        try:
            flag = ComplianceFlag.objects.get(pk=pk)
        except ComplianceFlag.DoesNotExist:
            return Response({'detail': 'Flag introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ComplianceFlagStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_status = serializer.validated_data['status']

        # Le flag OPEN → REVIEWED ou DISMISSED uniquement
        if flag.status != ComplianceFlag.FlagStatus.OPEN:
            return Response(
                {'detail': 'Seuls les flags OPEN peuvent être mis à jour.'},
                status=status.HTTP_409_CONFLICT,
            )

        flag.status      = new_status
        flag.reviewed_by = request.user
        flag.reviewed_at = timezone.now()
        flag.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        return Response(ComplianceFlagSerializer(flag).data)


class AuditReportListCreateView(APIView):
    """
    GET  /api/v5/audit/reports/ — liste des rapports existants
    POST /api/v5/audit/reports/ — génère un nouveau rapport (synchrone v1)
    """
    permission_classes = [IsAuditAdmin]

    def get(self, request):
        qs = AuditReport.objects.select_related('generated_by').order_by('-generated_at')[:100]
        return Response(AuditReportSerializer(qs, many=True).data)

    def post(self, request):
        serializer = AuditReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        report = serializer.save(
            generated_by=request.user,
            status=AuditReport.ReportStatus.PENDING,
        )

        # Génération synchrone — calcul des métriques pour la période
        try:
            summary = _compute_report_summary(report.period_start, report.period_end)
            report.summary = summary
            report.status  = AuditReport.ReportStatus.COMPLETE
        except Exception:
            logger.exception("Échec génération rapport audit pk=%s", report.pk)
            report.status = AuditReport.ReportStatus.FAILED

        report.save(update_fields=['summary', 'status'])
        return Response(AuditReportSerializer(report).data, status=status.HTTP_201_CREATED)


class AuditReportDetailView(APIView):
    """GET /api/v5/audit/reports/<pk>/"""
    permission_classes = [IsAuditReader]

    def get(self, request, pk):
        try:
            report = AuditReport.objects.select_related('generated_by').get(pk=pk)
        except AuditReport.DoesNotExist:
            return Response({'detail': 'Rapport introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AuditReportSerializer(report).data)


# ── Helpers internes ──────────────────────────────────────────────────────────

def _compute_report_summary(period_start: date, period_end: date) -> dict:
    """
    Calcule les métriques d'une période pour un rapport de conformité.
    Agrège VerificationLog + IntelAlert + ComplianceFlag.
    """
    from apps.biometric.models import VerificationLog
    from apps.intel.models import IntelAlert

    logs = VerificationLog.objects.filter(
        timestamp__date__gte=period_start,
        timestamp__date__lte=period_end,
    )

    by_status = dict(
        logs.values('status').annotate(c=Count('id')).values_list('status', 'c')
    )

    flags_period = ComplianceFlag.objects.filter(
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
    )

    return {
        'period_start':           str(period_start),
        'period_end':             str(period_end),
        'total_verifications':    logs.count(),
        'verifications_by_status': by_status,
        'intel_alerts_open':      IntelAlert.objects.filter(status='OPEN').count(),
        'intel_alerts_critical':  IntelAlert.objects.filter(
            status='OPEN', severity='CRITICAL'
        ).count(),
        'compliance_flags_new':   flags_period.count(),
        'compliance_flags_open':  ComplianceFlag.objects.filter(status='OPEN').count(),
        'audit_events_total':     AuditEvent.objects.filter(
            created_at__date__gte=period_start,
            created_at__date__lte=period_end,
        ).count(),
    }
