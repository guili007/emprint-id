"""
Vues Module 09 — Eyeshield Health.

GET/POST  /api/v9/health/patients/                → dossiers patients
GET       /api/v9/health/patients/<national_id>/  → dossier complet (visites + vaccins + ordonnances)
POST      /api/v9/health/visits/                  → enregistrer une consultation
POST      /api/v9/health/vaccinations/            → enregistrer une vaccination
POST      /api/v9/health/prescriptions/           → enregistrer une ordonnance
GET/POST  /api/v9/health/epidemio/                → alertes épidémiologiques
GET       /api/v9/health/stats/                   → dashboard agrégé
"""
import logging

from django.db.models import Count
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    EpidemioAlert,
    HealthPatient,
    HealthPrescription,
    HealthVaccination,
    HealthVisit,
)
from .permissions import IsHealthAdmin, IsHealthWorker
from .serializers import (
    EpidemioAlertCreateSerializer,
    EpidemioAlertSerializer,
    HealthPatientCreateSerializer,
    HealthPatientDetailSerializer,
    HealthPatientListSerializer,
    HealthPrescriptionCreateSerializer,
    HealthPrescriptionSerializer,
    HealthVaccinationCreateSerializer,
    HealthVaccinationSerializer,
    HealthVisitCreateSerializer,
    HealthVisitSerializer,
)

logger = logging.getLogger('emprint.health')


def _real_user(user):
    """Retourne l'utilisateur si c'est un vrai modèle Django, sinon None.
    Évite ValueError sur les FK en test avec un FakeUser."""
    from django.contrib.auth import get_user_model
    return user if isinstance(user, get_user_model()) else None


class HealthPatientListCreateView(APIView):
    """
    GET  /api/v9/health/patients/  — liste patients (filtres: blood_type, q=national_id)
    POST /api/v9/health/patients/  — créer un dossier médical
    """
    permission_classes = [IsHealthWorker]

    def get(self, request):
        qs = HealthPatient.objects.order_by('-created_at')

        blood_type = request.query_params.get('blood_type')
        if blood_type:
            qs = qs.filter(blood_type=blood_type)

        q = request.query_params.get('q')
        if q:
            qs = qs.filter(national_id__icontains=q)

        return Response(HealthPatientListSerializer(qs[:200], many=True).data)

    def post(self, request):
        serializer = HealthPatientCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        patient = serializer.save(created_by=_real_user(request.user))
        return Response(HealthPatientDetailSerializer(patient).data, status=status.HTTP_201_CREATED)


class HealthPatientDetailView(APIView):
    """
    GET /api/v9/health/patients/<national_id>/

    Retourne le dossier complet : données patient + historique
    visites, vaccinations, ordonnances, et taux couverture vaccinale.
    """
    permission_classes = [IsHealthWorker]

    def get(self, request, national_id):
        try:
            patient = HealthPatient.objects.get(national_id=national_id)
        except HealthPatient.DoesNotExist:
            return Response(
                {'detail': 'Dossier médical introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        coverage = vaccination_coverage(national_id)

        return Response({
            **HealthPatientDetailSerializer(patient).data,
            'vaccination_coverage': coverage,
        })


class HealthVisitCreateView(APIView):
    """
    POST /api/v9/health/visits/

    Enregistre une consultation.
    Si le dossier patient n'existe pas encore, il est créé automatiquement
    (get_or_create) — un agent de terrain peut enregistrer une visite sans
    passer d'abord par la création du dossier.
    """
    permission_classes = [IsHealthWorker]

    def post(self, request):
        serializer = HealthVisitCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        national_id = serializer.validated_data.pop('national_id')
        patient, _  = HealthPatient.objects.get_or_create(
            national_id=national_id,
            defaults={'created_by': _real_user(request.user)},
        )

        visit = HealthVisit.objects.create(
            patient=patient,
            agent=_real_user(request.user),
            **serializer.validated_data,
        )
        return Response(HealthVisitSerializer(visit).data, status=status.HTTP_201_CREATED)


class HealthVaccinationCreateView(APIView):
    """POST /api/v9/health/vaccinations/ — enregistrer un acte vaccinal."""
    permission_classes = [IsHealthWorker]

    def post(self, request):
        serializer = HealthVaccinationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        national_id = serializer.validated_data.pop('national_id')
        patient, _  = HealthPatient.objects.get_or_create(
            national_id=national_id,
            defaults={'created_by': _real_user(request.user)},
        )

        vaccination = HealthVaccination.objects.create(
            patient=patient,
            agent=_real_user(request.user),
            **serializer.validated_data,
        )
        return Response(HealthVaccinationSerializer(vaccination).data, status=status.HTTP_201_CREATED)


class HealthPrescriptionCreateView(APIView):
    """POST /api/v9/health/prescriptions/ — enregistrer une ordonnance."""
    permission_classes = [IsHealthWorker]

    def post(self, request):
        serializer = HealthPrescriptionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        national_id = serializer.validated_data.pop('national_id')
        patient, _  = HealthPatient.objects.get_or_create(
            national_id=national_id,
            defaults={'created_by': _real_user(request.user)},
        )

        prescription = HealthPrescription.objects.create(
            patient=patient,
            prescrit_par=_real_user(request.user),
            **serializer.validated_data,
        )
        return Response(HealthPrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)


class EpidemioAlertListCreateView(APIView):
    """
    GET  /api/v9/health/epidemio/  — alertes (filtres: statut, province, niveau)
    POST /api/v9/health/epidemio/  — créer une alerte (ROLE_ADMIN uniquement)
    """

    def get_permissions(self):
        # La lecture des alertes épidémio est réservée aux admins (données sensibles)
        return [IsHealthAdmin()]

    def get(self, request):
        qs = EpidemioAlert.objects.order_by('-date_debut')

        if statut := request.query_params.get('statut'):
            qs = qs.filter(statut=statut)
        if province := request.query_params.get('province'):
            qs = qs.filter(province__icontains=province)
        if niveau := request.query_params.get('niveau'):
            qs = qs.filter(niveau=niveau)

        return Response(EpidemioAlertSerializer(qs[:100], many=True).data)

    def post(self, request):
        serializer = EpidemioAlertCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        alert = serializer.save(created_by=_real_user(request.user))
        return Response(EpidemioAlertSerializer(alert).data, status=status.HTTP_201_CREATED)


class HealthStatsView(APIView):
    """GET /api/v9/health/stats/ — tableau de bord agrégé."""
    permission_classes = [IsHealthAdmin]

    def get(self, request):
        visits_by_type = dict(
            HealthVisit.objects.values('visit_type')
            .annotate(c=Count('id'))
            .values_list('visit_type', 'c')
        )

        top_vaccines = list(
            HealthVaccination.objects.values('vaccin_code')
            .annotate(c=Count('id'))
            .order_by('-c')[:10]
            .values('vaccin_code', 'c')
        )

        epidemio_active = dict(
            EpidemioAlert.objects.filter(statut='EN_COURS')
            .values('niveau')
            .annotate(c=Count('id'))
            .values_list('niveau', 'c')
        )

        return Response({
            'patients':  {'total': HealthPatient.objects.count()},
            'visits':    {'total': HealthVisit.objects.count(), 'by_type': visits_by_type},
            'vaccinations': {'total': HealthVaccination.objects.count(), 'top_vaccines': top_vaccines},
            'prescriptions': {'total': HealthPrescription.objects.count()},
            'epidemio':  {
                'total':  EpidemioAlert.objects.count(),
                'active': EpidemioAlert.objects.filter(statut='EN_COURS').count(),
                'active_by_level': epidemio_active,
            },
        })


# ── Helpers internes ──────────────────────────────────────────────────────────

def vaccination_coverage(national_id: str) -> dict:
    """
    Calcule la couverture vaccinale d'un patient par rapport au calendrier
    vaccinal national de la RDC.

    Retourne le nombre de vaccins reçus, le nombre de vaccins obligatoires
    couverts, et le taux de couverture en pourcentage.

    Retourne le nombre de vaccins reçus, le nombre de vaccins obligatoires
    couverts, et le taux de couverture en pourcentage.
    """
    REQUIRED_VACCINES = ['BCG', 'VPO', 'DTC', 'VPHB', 'RR', 'YELLOW_FEVER']

    received_codes = set(
        HealthVaccination.objects.filter(patient__national_id=national_id)
        .values_list('vaccin_code', flat=True)
        .distinct()
    )

    covered        = [v for v in REQUIRED_VACCINES if v in received_codes]
    missing        = [v for v in REQUIRED_VACCINES if v not in received_codes]
    total_required = len(REQUIRED_VACCINES)
    covered_count  = len(covered)

    coverage_pct = round(covered_count / total_required * 100, 1) if total_required else 0.0

    return {
        'received_count':  len(received_codes),
        'covered_count':   covered_count,
        'total_required':  total_required,
        'coverage_pct':    coverage_pct,
        'missing_vaccines': missing,
    }
