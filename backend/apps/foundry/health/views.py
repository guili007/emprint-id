"""
Views Foundry Health — dossier patient unifié + épidémiologie.

Endpoints :
  GET  /api/v3/foundry/health/patients/              liste + filtres
  GET  /api/v3/foundry/health/patients/<national_id>/ dossier complet
  POST /api/v3/foundry/health/visits/                enregistrer une visite
  POST /api/v3/foundry/health/vaccinations/          enregistrer une vaccination
  GET  /api/v3/foundry/health/epidemio/              alertes épidémio
  GET  /api/v3/foundry/health/stats/                 statistiques agrégées

Règle immuabilité : HealthVisit, HealthVaccination, HealthPrescription
ne sont jamais supprimées ni modifiées ici — création uniquement.
"""
import logging

from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError

from apps.foundry.models import (
    HealthPatient, HealthVisit, HealthVaccination,
    EpidemioAlert, SectorTenant,
)
from .permissions import IsHealthWorker, IsHealthAdmin
from .serializers import (
    HealthPatientListSerializer,
    HealthPatientDetailSerializer,
    HealthVisitSerializer,
    HealthVisitCreateSerializer,
    HealthVaccinationCreateSerializer,
    HealthVaccinationSerializer,
    EpidemioAlertSerializer,
)

logger = logging.getLogger('emprint.foundry.health')


class HealthPatientListView(APIView):
    """
    GET /api/v3/foundry/health/patients/

    Filtres :
      ?blood_type=A+
      ?q=<national_id partiel ou préfixe>
    """
    permission_classes = [IsHealthWorker]

    def get(self, request):
        qs = HealthPatient.objects.all()

        # Filtre groupe sanguin
        blood_type = request.query_params.get('blood_type')
        if blood_type:
            qs = qs.filter(blood_type=blood_type)

        # Recherche par national_id
        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(national_id__icontains=q)

        # Pagination 25/page
        page_size = 25
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            page = 1

        total = qs.count()
        start = (page - 1) * page_size

        serializer = HealthPatientListSerializer(qs[start:start + page_size], many=True)
        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'results': serializer.data,
        })


class HealthPatientDetailView(APIView):
    """
    GET /api/v3/foundry/health/patients/<national_id>/

    Retourne le dossier complet : infos patient + visites + vaccinations + prescriptions.
    prefetch_related évite les requêtes N+1.
    """
    permission_classes = [IsHealthWorker]

    def get(self, request, national_id):
        try:
            patient = HealthPatient.objects.prefetch_related(
                'visits', 'vaccinations', 'prescriptions'
            ).get(national_id=national_id)
        except HealthPatient.DoesNotExist:
            raise NotFound("Dossier patient introuvable.")

        serializer = HealthPatientDetailSerializer(patient)
        return Response(serializer.data)


class HealthVisitView(APIView):
    """
    POST /api/v3/foundry/health/visits/

    Enregistre une visite médicale.
    Si le patient n'existe pas encore, crée automatiquement son dossier.
    La visite est IMMUABLE après création (append-only).
    """
    permission_classes = [IsHealthWorker]

    def post(self, request):
        serializer = HealthVisitCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Récupérer l'établissement de santé
        try:
            facility = SectorTenant.objects.get(id=data['facility_id'], sector='HEALTH')
        except SectorTenant.DoesNotExist:
            raise ValidationError({"facility_id": "Établissement HEALTH introuvable."})

        # Créer le dossier patient s'il n'existe pas
        patient, _ = HealthPatient.objects.get_or_create(
            national_id=data['patient_national_id'],
            defaults={'created_by_facility': facility},
        )

        # Enregistrer la visite (append-only)
        visit = HealthVisit.objects.create(
            patient=patient,
            facility=facility,
            agent=request.user,
            type_visite=data['type_visite'],
            motif=data['motif'],
            diagnostic_code=data.get('diagnostic_code', ''),
            diagnostic_libelle=data.get('diagnostic_libelle', ''),
        )

        logger.info(
            "Visite enregistrée : patient=%s, facility=%s, type=%s",
            patient.national_id, facility.name, visit.type_visite,
        )

        return Response(HealthVisitSerializer(visit).data, status=201)


class HealthVaccinationView(APIView):
    """
    POST /api/v3/foundry/health/vaccinations/

    Enregistre une vaccination dans le carnet vaccinal numérique.
    Le dossier patient doit exister (créé via une visite préalable).
    La vaccination est IMMUABLE après création (append-only).
    """
    permission_classes = [IsHealthWorker]

    def post(self, request):
        serializer = HealthVaccinationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Vérifier que le dossier patient existe
        try:
            patient = HealthPatient.objects.get(national_id=data['patient_national_id'])
        except HealthPatient.DoesNotExist:
            raise ValidationError({
                "patient_national_id": "Aucun dossier trouvé pour cet ID. "
                                       "Créer d'abord une visite."
            })

        # Récupérer l'établissement
        try:
            facility = SectorTenant.objects.get(id=data['facility_id'], sector='HEALTH')
        except SectorTenant.DoesNotExist:
            raise ValidationError({"facility_id": "Établissement HEALTH introuvable."})

        # Enregistrer la vaccination (append-only)
        vaccination = HealthVaccination.objects.create(
            patient=patient,
            facility=facility,
            agent=request.user,
            vaccin_nom=data['vaccin_nom'],
            vaccin_code=data['vaccin_code'],
            dose_numero=data['dose_numero'],
            date_administration=data['date_administration'],
            lot_numero=data.get('lot_numero', ''),
        )

        return Response(HealthVaccinationSerializer(vaccination).data, status=201)


class EpidemioAlertView(APIView):
    """
    GET /api/v3/foundry/health/epidemio/

    Dashboard épidémiologique — données mock v1.
    Intégration DHIS2 prévue pour v2.

    Filtres :
      ?statut=EN_COURS|SURVEILLE|RESOLU
      ?province=<nom>
      ?niveau=FAIBLE|MODERE|ELEVE|CRITIQUE
    """
    permission_classes = [IsHealthAdmin]

    def get(self, request):
        qs = EpidemioAlert.objects.all()

        statut = request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        province = request.query_params.get('province')
        if province:
            qs = qs.filter(province__icontains=province)

        niveau = request.query_params.get('niveau')
        if niveau:
            qs = qs.filter(niveau=niveau)

        serializer = EpidemioAlertSerializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})


class HealthStatsView(APIView):
    """
    GET /api/v3/foundry/health/stats/

    Statistiques agrégées :
      - Total patients enregistrés
      - Visites par type
      - Top 5 diagnostics (ICD-10)
      - Total vaccinations par vaccin
    """
    permission_classes = [IsHealthAdmin]

    def get(self, request):
        # Répartition des visites par type
        by_type = dict(
            HealthVisit.objects.values('type_visite')
            .annotate(count=Count('id'))
            .values_list('type_visite', 'count')
        )

        # Top 5 diagnostics (ICD-10) — exclut les visites sans diagnostic
        top_diagnostics = list(
            HealthVisit.objects.exclude(diagnostic_code='')
            .values('diagnostic_code', 'diagnostic_libelle')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        # Vaccinations par code vaccin
        by_vaccin = list(
            HealthVaccination.objects.values('vaccin_code')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # Alertes épidémio actives (EN_COURS ou SURVEILLE)
        alertes_actives = EpidemioAlert.objects.filter(
            statut__in=[EpidemioAlert.Statut.EN_COURS, EpidemioAlert.Statut.SURVEILLE]
        ).count()

        return Response({
            'total_patients': HealthPatient.objects.count(),
            'total_visits':   HealthVisit.objects.count(),
            'visits_by_type': by_type,
            'top_diagnostics': top_diagnostics,
            'vaccinations_by_code': by_vaccin,
            'alertes_epidemio_actives': alertes_actives,
        })
