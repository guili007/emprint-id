"""
Views Foundry Edu — dossiers scolaires EduFirst (cache local).

Endpoints :
  GET  /api/v3/foundry/edu/students/                  liste + filtres
  GET  /api/v3/foundry/edu/students/<national_id>/    dossier complet (national_id lié)
  GET  /api/v3/foundry/edu/students/by-matricule/<m>/ dossier par matricule EduFirst
  GET  /api/v3/foundry/edu/schools/                   liste des écoles synchronisées
  GET  /api/v3/foundry/edu/stats/                     statistiques agrégées (admin)

Données issues du cache local sync_edufirst — jamais d'appel direct à api.edufirst.pro.
"""
import logging

from django.db.models import Count, Avg, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

from apps.foundry.models import EduSchool, EduStudent, EduBulletin
from .permissions import IsEduReader, IsEduAdmin
from .serializers import (
    EduSchoolSerializer,
    EduStudentListSerializer,
    EduStudentDetailSerializer,
)

logger = logging.getLogger('emprint.foundry.edu')


class EduStudentListView(APIView):
    """
    GET /api/v3/foundry/edu/students/

    Filtres :
      ?school_id=<edufirst_school_id>   — école spécifique
      ?annee=2025-2026                   — élèves ayant un bulletin pour cette année
      ?q=<nom ou matricule>              — recherche textuelle
      ?linked_only=true                  — uniquement les élèves liés à un national_id
    """
    permission_classes = [IsEduReader]

    def get(self, request):
        qs = EduStudent.objects.select_related('school').all()

        # Filtre par école
        school_id = request.query_params.get('school_id')
        if school_id:
            qs = qs.filter(school__edufirst_school_id=school_id)

        # Filtre par année scolaire (via les bulletins)
        annee = request.query_params.get('annee')
        if annee:
            qs = qs.filter(bulletins__annee_scolaire=annee).distinct()

        # Filtre élèves avec national_id lié
        linked_only = request.query_params.get('linked_only', '').lower() == 'true'
        if linked_only:
            qs = qs.exclude(national_id__isnull=True).exclude(national_id='')

        # Recherche par nom ou matricule
        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(matricule__icontains=q)
            )

        # Pagination 25/page
        page_size = 25
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            page = 1

        total = qs.count()
        start = (page - 1) * page_size

        serializer = EduStudentListSerializer(qs[start:start + page_size], many=True)
        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'results': serializer.data,
        })


class EduStudentByNationalIdView(APIView):
    """
    GET /api/v3/foundry/edu/students/<national_id>/

    Dossier scolaire complet pour un citoyen identifié par son national_id EmPrint-iD.
    L'élève doit avoir été lié via une vérification biométrique préalable.
    Retourne tous ses bulletins avec le détail par matière.
    """
    permission_classes = [IsEduReader]

    def get(self, request, national_id):
        try:
            student = EduStudent.objects.prefetch_related(
                'bulletins__notes', 'school'
            ).get(national_id=national_id)
        except EduStudent.DoesNotExist:
            raise NotFound(
                "Aucun dossier scolaire lié à cet ID national. "
                "La vérification biométrique est peut-être incomplète."
            )

        logger.info("Consultation dossier scolaire : national_id=%s", national_id)
        serializer = EduStudentDetailSerializer(student)
        return Response(serializer.data)


class EduStudentByMatriculeView(APIView):
    """
    GET /api/v3/foundry/edu/students/by-matricule/<matricule>/

    Recherche par matricule EduFirst (ex. KAMPAL-7K4M).
    Utilisé par les agents qui ont le matricule imprimé sur la carte scolaire.
    """
    permission_classes = [IsEduReader]

    def get(self, request, matricule):
        try:
            student = EduStudent.objects.prefetch_related(
                'bulletins__notes', 'school'
            ).get(matricule__iexact=matricule)
        except EduStudent.DoesNotExist:
            raise NotFound("Matricule scolaire introuvable.")

        serializer = EduStudentDetailSerializer(student)
        return Response(serializer.data)


class EduSchoolListView(APIView):
    """
    GET /api/v3/foundry/edu/schools/

    Liste des écoles EduFirst synchronisées dans le cache local.
    """
    permission_classes = [IsEduReader]

    def get(self, request):
        qs = EduSchool.objects.filter(is_active=True).order_by('country', 'name')
        serializer = EduSchoolSerializer(qs, many=True)
        return Response({
            'count': qs.count(),
            'results': serializer.data,
        })


class EduStatsView(APIView):
    """
    GET /api/v3/foundry/edu/stats/

    Statistiques agrégées :
      - Total élèves en cache
      - Total élèves liés à un national_id EmPrint-iD
      - Total bulletins synchronisés
      - Moyenne générale par mention
      - Dernière synchronisation par école
    """
    permission_classes = [IsEduAdmin]

    def get(self, request):
        total_students = EduStudent.objects.count()
        linked_students = EduStudent.objects.exclude(
            national_id__isnull=True
        ).exclude(national_id='').count()
        total_bulletins = EduBulletin.objects.count()

        # Répartition des bulletins par mention
        by_mention = dict(
            EduBulletin.objects.values('mention')
            .annotate(count=Count('id'))
            .values_list('mention', 'count')
        )

        # Moyenne globale (sur tous les bulletins)
        avg_result = EduBulletin.objects.aggregate(avg=Avg('moyenne'))
        moyenne_globale = round(float(avg_result['avg'] or 0), 2)

        # Dernière sync par école
        schools = EduSchool.objects.values('name', 'last_synced').order_by('name')
        sync_status = [
            {'school': s['name'], 'last_synced': s['last_synced']}
            for s in schools
        ]

        return Response({
            'total_students':      total_students,
            'linked_students':     linked_students,
            'link_rate_pct':       round(linked_students / total_students * 100, 1)
                                   if total_students else 0,
            'total_bulletins':     total_bulletins,
            'bulletins_by_mention': by_mention,
            'moyenne_globale':     moyenne_globale,
            'sync_status':         sync_status,
        })
