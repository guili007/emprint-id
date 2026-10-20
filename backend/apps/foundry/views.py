"""Views Module 03 — Eyeshield Foundry Banking."""
import logging

from django.utils import timezone
from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.citizens.models import Citizen
from .models import SectorTenant, TenantAgent, FraudAlert, KYCRecord
from .permissions import IsBankAgent, IsBankTenantAdmin, IsFoundryAdmin
from .serializers import FraudAlertSerializer
from .fraud import _severity_for_count, FRAUD_WINDOW_MINUTES

logger = logging.getLogger('emprint.foundry')


class KYCView(APIView):
    """
    POST /api/v3/foundry/banking/kyc/

    Vérification KYC bancaire.
    Retourne uniquement CONFORME/NON_CONFORME — jamais d'info watchlist (Silent Flagging).
    Détection fraude automatique si même ID dans ≥ 2 banques sur la fenêtre.
    """
    permission_classes = [IsBankAgent]

    def post(self, request):
        national_id = request.data.get('national_id', '').strip()
        if not national_id:
            return Response({'error': 'national_id requis.'}, status=status.HTTP_400_BAD_REQUEST)

        tenant_membership = (
            TenantAgent.objects
            .select_related('tenant')
            .filter(user=request.user, tenant__is_active=True, tenant__sector='BANKING')
            .first()
        )
        if not tenant_membership:
            return Response({'error': 'Tenant introuvable.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = tenant_membership.tenant

        try:
            citizen = Citizen.objects.get(national_id=national_id, is_active=True)
        except Citizen.DoesNotExist:
            kyc_status = KYCRecord.KYCStatus.NON_CONFORME
            _record_kyc(national_id, tenant, request.user, kyc_status)
            return Response({'kyc_status': kyc_status, 'tenant': tenant.name})

        has_embedding = hasattr(citizen, 'face_embedding')
        kyc_status = (
            KYCRecord.KYCStatus.CONFORME
            if has_embedding
            else KYCRecord.KYCStatus.NON_CONFORME
        )

        _record_kyc(national_id, tenant, request.user, kyc_status)
        _detect_fraud(national_id)

        return Response({'kyc_status': kyc_status, 'tenant': tenant.name})


class FraudAlertListView(APIView):
    """
    GET /api/v3/foundry/banking/fraud-alerts/

    Liste les alertes fraude non résolues.
    - Admin tenant bancaire : voit les alertes de son secteur
    - ROLE_ADMIN / ROLE_WATCHLIST_ADMIN : voit toutes les alertes
    """
    def get_permissions(self):
        role = getattr(self.request.user, 'role', '')
        if role in ('ROLE_ADMIN', 'ROLE_WATCHLIST_ADMIN'):
            return [IsFoundryAdmin()]
        return [IsBankTenantAdmin()]

    def get(self, request):
        alerts = FraudAlert.objects.filter(is_resolved=False).order_by('-detected_at')
        serializer = FraudAlertSerializer(alerts, many=True)
        return Response({'count': alerts.count(), 'results': serializer.data})


# ── helpers ───────────────────────────────────────────────────────────────────

def _record_kyc(national_id, tenant, agent, kyc_status):
    KYCRecord.objects.create(
        national_id=national_id,
        tenant=tenant,
        agent=agent,
        status=kyc_status,
    )


def _detect_fraud(national_id):
    """Vérifie si le même national_id a été vérifié par plusieurs tenants."""
    cutoff = timezone.now() - timedelta(minutes=FRAUD_WINDOW_MINUTES)
    distinct_tenants = (
        KYCRecord.objects
        .filter(national_id=national_id, created_at__gte=cutoff)
        .values('tenant')
        .distinct()
    )
    count = distinct_tenants.count()
    if count < 2:
        return

    severity = _severity_for_count(count)
    tenant_ids = [row['tenant'] for row in distinct_tenants]
    tenant_names = list(
        SectorTenant.objects.filter(id__in=tenant_ids).values_list('name', flat=True)
    )

    FraudAlert.objects.create(
        national_id=national_id,
        severity=severity,
        tenant_count=count,
        tenant_names=tenant_names,
        window_minutes=FRAUD_WINDOW_MINUTES,
    )
    logger.warning(
        'Alerte fraude [%s] national_id=%s × %d tenants: %s',
        severity, national_id, count, tenant_names,
    )
