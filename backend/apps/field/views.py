"""
Vues Module 07 — Eyeshield Field.

GET      /api/v7/field/agents/           → liste des agents terrain
GET      /api/v7/field/missions/         → liste des missions
POST     /api/v7/field/missions/         → créer une mission
GET      /api/v7/field/missions/<pk>/    → détail mission
POST     /api/v7/field/sync/             → synchronisation différée (batch)
GET      /api/v7/field/records/          → liste des enregistrements
GET      /api/v7/field/stats/            → dashboard agrégé
"""
import logging

from django.db.models import Avg, Count, F
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FieldAgent, FieldMission, FieldRecord, SyncBatch
from .permissions import IsFieldReader, IsFieldWriter
from .serializers import (
    FieldAgentSerializer,
    FieldMissionCreateSerializer,
    FieldMissionSerializer,
    FieldRecordSerializer,
    SyncBatchInputSerializer,
    SyncBatchSerializer,
)

logger = logging.getLogger('emprint.field')


class FieldAgentListView(APIView):
    """GET /api/v7/field/agents/ — agents terrain (filtres: status, province)"""
    permission_classes = [IsFieldReader]

    def get(self, request):
        qs = FieldAgent.objects.select_related('agent').order_by('-created_at')

        zone = request.query_params.get('province')
        if zone:
            qs = qs.filter(zone_province=zone)

        agent_status = request.query_params.get('status')
        if agent_status:
            qs = qs.filter(status=agent_status)

        return Response(FieldAgentSerializer(qs[:100], many=True).data)


class FieldMissionListCreateView(APIView):
    """
    GET  /api/v7/field/missions/ — liste (filtres: agent, status, mission_type)
    POST /api/v7/field/missions/ — créer une mission
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsFieldWriter()]
        return [IsFieldReader()]

    def get(self, request):
        qs = FieldMission.objects.select_related('agent__agent').order_by('-assigned_at')

        mis_status = request.query_params.get('status')
        if mis_status:
            qs = qs.filter(status=mis_status)

        mis_type = request.query_params.get('mission_type')
        if mis_type:
            qs = qs.filter(mission_type=mis_type)

        agent_id = request.query_params.get('agent_id')
        if agent_id:
            qs = qs.filter(agent_id=agent_id)

        return Response(FieldMissionSerializer(qs[:100], many=True).data)

    def post(self, request):
        serializer = FieldMissionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        mission = serializer.save(assigned_by=request.user)
        return Response(FieldMissionSerializer(mission).data, status=status.HTTP_201_CREATED)


class FieldMissionDetailView(APIView):
    """GET /api/v7/field/missions/<pk>/"""
    permission_classes = [IsFieldReader]

    def get(self, request, pk):
        try:
            mission = FieldMission.objects.select_related('agent__agent', 'assigned_by').get(pk=pk)
        except FieldMission.DoesNotExist:
            return Response({'detail': 'Mission introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(FieldMissionSerializer(mission).data)


class FieldSyncView(APIView):
    """
    POST /api/v7/field/sync/
    Synchronisation différée — reçoit un batch de records créés hors-ligne.

    Idempotent : un record déjà présent (même agent + offline_at + national_id)
    est compté comme duplicate et ignoré sans erreur.
    """
    permission_classes = [IsFieldWriter]

    def post(self, request):
        serializer = SyncBatchInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        device_id = data['device_id']
        records_data = data['records']

        # Récupère ou crée le profil FieldAgent pour cet utilisateur
        field_agent, _ = FieldAgent.objects.get_or_create(
            agent=request.user,
            defaults={'device_id': device_id},
        )
        if device_id and field_agent.device_id != device_id:
            field_agent.device_id = device_id
            field_agent.save(update_fields=['device_id'])

        batch = SyncBatch.objects.create(
            field_agent=field_agent,
            device_id=device_id,
            records_count=len(records_data),
            status=SyncBatch.BatchStatus.PENDING,
        )

        accepted, duplicates, errors = _process_sync_records(field_agent, records_data)

        # Mise à jour du batch avec les résultats
        batch.accepted_count  = accepted
        batch.duplicate_count = duplicates
        batch.error_log       = errors
        batch.status = (
            SyncBatch.BatchStatus.COMPLETE if not errors else SyncBatch.BatchStatus.PARTIAL
        )
        batch.save(update_fields=['accepted_count', 'duplicate_count', 'error_log', 'status'])

        # Met à jour last_sync_at sur l'agent
        field_agent.last_sync_at = timezone.now()
        field_agent.save(update_fields=['last_sync_at'])

        return Response(SyncBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class FieldRecordListView(APIView):
    """GET /api/v7/field/records/ — enregistrements terrain (filtres: agent, type, date)"""
    permission_classes = [IsFieldReader]

    def get(self, request):
        qs = FieldRecord.objects.select_related('field_agent__agent').order_by('-offline_at')

        record_type = request.query_params.get('record_type')
        if record_type:
            qs = qs.filter(record_type=record_type)

        national_id = request.query_params.get('national_id')
        if national_id:
            qs = qs.filter(national_id=national_id)

        agent_id = request.query_params.get('agent_id')
        if agent_id:
            qs = qs.filter(field_agent_id=agent_id)

        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(offline_at__date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(offline_at__date__lte=date_to)

        return Response(FieldRecordSerializer(qs[:200], many=True).data)


class FieldStatsView(APIView):
    """GET /api/v7/field/stats/ — dashboard agrégé agents terrain"""
    permission_classes = [IsFieldReader]

    def get(self, request):
        today = timezone.now().date()

        records_by_type = dict(
            FieldRecord.objects.values('record_type')
            .annotate(c=Count('id'))
            .values_list('record_type', 'c')
        )

        missions_by_status = dict(
            FieldMission.objects.values('status')
            .annotate(c=Count('id'))
            .values_list('status', 'c')
        )

        return Response({
            'agents': {
                'total':  FieldAgent.objects.count(),
                'active': FieldAgent.objects.filter(status='ACTIVE').count(),
            },
            'missions': {
                'total':      FieldMission.objects.count(),
                'by_status':  missions_by_status,
                'due_today':  FieldMission.objects.filter(
                    due_date=today, status__in=['PENDING', 'IN_PROGRESS']
                ).count(),
            },
            'records': {
                'total':    FieldRecord.objects.count(),
                'today':    FieldRecord.objects.filter(synced_at__date=today).count(),
                'by_type':  records_by_type,
            },
            'sync_batches_today': SyncBatch.objects.filter(synced_at__date=today).count(),
        })


# ── Helpers internes ──────────────────────────────────────────────────────────

def _process_sync_records(field_agent: FieldAgent, records_data: list) -> tuple:
    """
    Traite chaque record du batch de synchronisation.
    Retourne (accepted, duplicates, errors_list).

    Idempotence : si un record identique (même agent + offline_at + national_id
    + record_type) existe déjà, il est compté comme duplicate et ignoré.
    """
    accepted = 0
    duplicates = 0
    errors = []

    for i, rec in enumerate(records_data):
        try:
            # Vérification de doublon avant insertion
            is_duplicate = _is_duplicate_record(field_agent, rec)

            if is_duplicate:
                duplicates += 1
                continue

            # Résolution de la mission associée si fournie
            mission = None
            if rec.get('mission_id'):
                try:
                    mission = FieldMission.objects.get(
                        pk=rec['mission_id'], field_agent=field_agent
                    )
                except FieldMission.DoesNotExist:
                    pass

            FieldRecord.objects.create(
                field_agent  = field_agent,
                mission      = mission,
                record_type  = rec['record_type'],
                national_id  = rec.get('national_id', ''),
                description  = rec.get('description', ''),
                coordinates  = rec.get('coordinates', {}),
                province     = rec.get('province', ''),
                territoire   = rec.get('territoire', ''),
                offline_at   = rec['offline_at'],
                evidence     = rec.get('evidence', {}),
            )
            accepted += 1

        except Exception as exc:
            logger.exception("Sync record %d rejeté pour agent %s", i, field_agent.pk)
            errors.append({'index': i, 'error': str(exc)})

    return accepted, duplicates, errors


def _is_duplicate_record(field_agent: FieldAgent, rec: dict) -> bool:
    """
    Vérifie si un record identique existe déjà pour cet agent.

    Un doublon est défini par la combinaison :
      - field_agent
      - offline_at  (même timestamp)
      - national_id (même citoyen, ou tous deux vides)
      - record_type (même type d'événement)
    """
    return FieldRecord.objects.filter(
        field_agent=field_agent,
        offline_at=rec['offline_at'],
        national_id=rec.get('national_id', ''),
        record_type=rec['record_type'],
    ).exists()
