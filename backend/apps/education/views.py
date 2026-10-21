"""
Vues Module 10 — Eyeshield Education.

GET/POST  /api/v10/education/students/                → dossiers scolaires
GET       /api/v10/education/students/<national_id>/  → profil complet (résultats + diplômes + alertes)
POST      /api/v10/education/results/                 → enregistrer résultats
GET/POST  /api/v10/education/diplomas/                → diplômes nationaux
GET/POST  /api/v10/education/alerts/                  → alertes scolaires
GET       /api/v10/education/stats/                   → dashboard agrégé
"""
import logging

from django.db.models import Avg, Count
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AcademicResult, Diploma, SchoolAlert, StudentRecord
from .permissions import IsEduAdmin, IsEduWorker
from .serializers import (
    AcademicResultCreateSerializer,
    AcademicResultSerializer,
    DiplomaCreateSerializer,
    DiplomaSerializer,
    SchoolAlertCreateSerializer,
    SchoolAlertSerializer,
    StudentRecordCreateSerializer,
    StudentRecordDetailSerializer,
    StudentRecordListSerializer,
)

logger = logging.getLogger('emprint.education')


def _real_user(user):
    """Retourne l'utilisateur si c'est un vrai modèle Django, sinon None."""
    from django.contrib.auth import get_user_model
    return user if isinstance(user, get_user_model()) else None


class StudentRecordListCreateView(APIView):
    """
    GET  /api/v10/education/students/  — liste (filtres: national_id, province, niveau, statut)
    POST /api/v10/education/students/  — créer un dossier scolaire
    """
    permission_classes = [IsEduWorker]

    def get(self, request):
        qs = StudentRecord.objects.order_by('-school_year')

        if national_id := request.query_params.get('national_id'):
            qs = qs.filter(national_id=national_id)
        if province := request.query_params.get('province'):
            qs = qs.filter(province__icontains=province)
        if niveau := request.query_params.get('niveau'):
            qs = qs.filter(niveau=niveau)
        if statut := request.query_params.get('statut'):
            qs = qs.filter(statut=statut)

        return Response(StudentRecordListSerializer(qs[:200], many=True).data)

    def post(self, request):
        serializer = StudentRecordCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        record = serializer.save(created_by=_real_user(request.user))
        return Response(StudentRecordDetailSerializer(record).data, status=status.HTTP_201_CREATED)


class StudentProfileView(APIView):
    """
    GET /api/v10/education/students/<national_id>/

    Profil éducatif complet : tous les dossiers scolaires + diplômes + alertes actives
    + score de risque d'abandon calculé par academic_risk_score().
    """
    permission_classes = [IsEduWorker]

    def get(self, request, national_id):
        records  = StudentRecord.objects.filter(national_id=national_id).prefetch_related('results')
        diplomas = Diploma.objects.filter(national_id=national_id)
        alerts   = SchoolAlert.objects.filter(national_id=national_id, statut='OUVERT')

        if not records.exists():
            return Response(
                {'detail': 'Dossier scolaire introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        risk = academic_risk_score(national_id)

        return Response({
            'national_id':    national_id,
            'records':        StudentRecordDetailSerializer(records, many=True).data,
            'diplomas':       DiplomaSerializer(diplomas, many=True).data,
            'active_alerts':  SchoolAlertSerializer(alerts, many=True).data,
            'academic_risk':  risk,
        })


class AcademicResultCreateView(APIView):
    """POST /api/v10/education/results/ — enregistrer des résultats scolaires."""
    permission_classes = [IsEduWorker]

    def post(self, request):
        serializer = AcademicResultCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        result = serializer.save(agent=_real_user(request.user))
        return Response(AcademicResultSerializer(result).data, status=status.HTTP_201_CREATED)


class DiplomaListCreateView(APIView):
    """
    GET  /api/v10/education/diplomas/  — liste (filtres: national_id, type_diplome, annee)
    POST /api/v10/education/diplomas/  — enregistrer un diplôme
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsEduWorker()]
        return [IsEduWorker()]

    def get(self, request):
        qs = Diploma.objects.order_by('-annee_obtention')

        if national_id := request.query_params.get('national_id'):
            qs = qs.filter(national_id=national_id)
        if type_diplome := request.query_params.get('type_diplome'):
            qs = qs.filter(type_diplome=type_diplome)
        if annee := request.query_params.get('annee'):
            qs = qs.filter(annee_obtention=annee)

        return Response(DiplomaSerializer(qs[:200], many=True).data)

    def post(self, request):
        serializer = DiplomaCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        diploma = serializer.save(created_by=_real_user(request.user))
        return Response(DiplomaSerializer(diploma).data, status=status.HTTP_201_CREATED)


class SchoolAlertListCreateView(APIView):
    """
    GET  /api/v10/education/alerts/  — alertes (filtres: national_id, alert_type, statut)
    POST /api/v10/education/alerts/  — créer une alerte
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsEduWorker()]
        return [IsEduWorker()]

    def get(self, request):
        qs = SchoolAlert.objects.order_by('-created_at')

        if national_id := request.query_params.get('national_id'):
            qs = qs.filter(national_id=national_id)
        if alert_type := request.query_params.get('alert_type'):
            qs = qs.filter(alert_type=alert_type)
        if statut := request.query_params.get('statut'):
            qs = qs.filter(statut=statut)

        return Response(SchoolAlertSerializer(qs[:200], many=True).data)

    def post(self, request):
        serializer = SchoolAlertCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        alert = serializer.save(issued_by=_real_user(request.user))
        return Response(SchoolAlertSerializer(alert).data, status=status.HTTP_201_CREATED)


class EducationStatsView(APIView):
    """GET /api/v10/education/stats/ — tableau de bord agrégé."""
    permission_classes = [IsEduAdmin]

    def get(self, request):
        students_by_niveau = dict(
            StudentRecord.objects.values('niveau')
            .annotate(c=Count('id'))
            .values_list('niveau', 'c')
        )

        students_by_statut = dict(
            StudentRecord.objects.values('statut')
            .annotate(c=Count('id'))
            .values_list('statut', 'c')
        )

        diplomas_by_type = dict(
            Diploma.objects.values('type_diplome')
            .annotate(c=Count('id'))
            .values_list('type_diplome', 'c')
        )

        alerts_by_type = dict(
            SchoolAlert.objects.filter(statut='OUVERT')
            .values('alert_type')
            .annotate(c=Count('id'))
            .values_list('alert_type', 'c')
        )

        return Response({
            'students': {
                'total':      StudentRecord.objects.count(),
                'by_niveau':  students_by_niveau,
                'by_statut':  students_by_statut,
            },
            'results': {
                'total':      AcademicResult.objects.count(),
                'moyenne_nationale': AcademicResult.objects.aggregate(m=Avg('note'))['m'],
            },
            'diplomas': {
                'total':    Diploma.objects.count(),
                'by_type':  diplomas_by_type,
            },
            'alerts': {
                'total':   SchoolAlert.objects.count(),
                'open':    SchoolAlert.objects.filter(statut='OUVERT').count(),
                'by_type': alerts_by_type,
            },
        })


# ── Helpers internes ──────────────────────────────────────────────────────────

def academic_risk_score(national_id: str) -> dict:
    """
    Calcule un score de risque d'abandon scolaire pour un élève.

    Facteurs pris en compte :
      - Moyenne générale (note faible = risque élevé)
      - Alertes ouvertes de type ABANDON ou VULNERABLE
      - Présence d'un dossier à statut ABANDONNE dans l'historique

    TODO(human): Implémenter la logique de calcul du score de risque académique.

    La fonction doit :
    1. Récupérer les résultats de l'élève (AcademicResult) et calculer la moyenne
    2. Compter les alertes ouvertes ABANDON + VULNERABLE (SchoolAlert)
    3. Vérifier si un dossier StudentRecord a statut ABANDONNE dans le passé
    4. Calculer un score de 0 à 100 :
         - Si moyenne < 50 : +40 points
         - Si moyenne entre 50 et 60 : +20 points
         - Par alerte ABANDON/VULNERABLE ouverte : +20 points (max +40)
         - Si historique d'abandon : +30 points
         - Clamp à 100
    5. Déduire un niveau : LOW (0-30), MEDIUM (31-60), HIGH (61-80), CRITICAL (81+)
    6. Retourner un dict avec : score, level, avg_note, open_alerts, has_dropout_history
    """
    pass
