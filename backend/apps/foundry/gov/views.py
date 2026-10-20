"""
Views Foundry Gov — dashboard opérationnel pour les Ministères.

Toutes ces vues lisent le CACHE LOCAL (GovEmployee, etc.).
Elles ne contactent JAMAIS SIGA directement — c'est le rôle de `sync_siga`.

Endpoints :
  GET /api/v3/foundry/gov/employees/          liste + filtres
  GET /api/v3/foundry/gov/employees/<uuid>/   détail + carrière
  GET /api/v3/foundry/gov/stats/              effectifs par ministère
  GET /api/v3/foundry/gov/budget/             lignes budgétaires (mock v1)
  GET /api/v3/foundry/gov/contracts/          marchés publics (mock v1)
"""
from django.db.models import Count, Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

from apps.foundry.models import GovEmployee, GovBudgetLine, GovContract
from .permissions import IsGovReader, IsGovAdmin
from .serializers import (
    GovEmployeeSerializer, GovEmployeeDetailSerializer,
    GovBudgetLineSerializer, GovContractSerializer,
)


class GovEmployeeListView(APIView):
    """
    GET /api/v3/foundry/gov/employees/

    Filtres disponibles :
      ?statut=ACTIF|RETRAITE|SUSPENDU|...
      ?administration=<nom>
      ?q=<matricule ou nom>
    """
    permission_classes = [IsGovReader]

    def get(self, request):
        qs = GovEmployee.objects.all()

        # Filtre par statut (ex. ?statut=ACTIF)
        statut = request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        # Filtre par nom de ministère (ex. ?administration=Finances)
        administration = request.query_params.get('administration')
        if administration:
            qs = qs.filter(administration_nom__icontains=administration)

        # Recherche libre sur matricule, nom, postnom
        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(matricule__icontains=q)
                | Q(nom__icontains=q)
                | Q(postnom__icontains=q)
            )

        # Pagination manuelle légère (25 par page, cohérent avec Module 02)
        page_size = 25
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            page = 1

        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size

        serializer = GovEmployeeSerializer(qs[start:end], many=True)
        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'results': serializer.data,
        })


class GovEmployeeDetailView(APIView):
    """
    GET /api/v3/foundry/gov/employees/<siga_uuid>/

    Retourne l'employé + ses événements de carrière (snapshot SIGA).
    """
    permission_classes = [IsGovReader]

    def get(self, request, siga_uuid):
        try:
            employee = GovEmployee.objects.prefetch_related('career_events').get(
                siga_uuid=siga_uuid
            )
        except GovEmployee.DoesNotExist:
            raise NotFound("Fonctionnaire introuvable dans le cache Gov.")

        serializer = GovEmployeeDetailSerializer(employee)
        return Response(serializer.data)


class GovStatsView(APIView):
    """
    GET /api/v3/foundry/gov/stats/

    Statistiques agrégées sur les fonctionnaires en cache.
    Réservé à ROLE_ADMIN / ROLE_WATCHLIST_ADMIN.
    """
    permission_classes = [IsGovAdmin]

    def get(self, request):
        # Effectifs par statut
        by_statut = dict(
            GovEmployee.objects.values('statut')
            .annotate(count=Count('id'))
            .values_list('statut', 'count')
        )

        # Effectifs par administration (top 10)
        by_admin = list(
            GovEmployee.objects.filter(statut=GovEmployee.Statut.ACTIF)
            .values('administration_nom')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        return Response({
            'total_employees': GovEmployee.objects.count(),
            'actifs': by_statut.get(GovEmployee.Statut.ACTIF, 0),
            'retraites': by_statut.get(GovEmployee.Statut.RETRAITE, 0),
            'by_statut': by_statut,
            'top_administrations': by_admin,
        })


class GovBudgetView(APIView):
    """
    GET /api/v3/foundry/gov/budget/

    Lignes budgétaires — données mock pour v1.
    Filtre : ?annee=2026&ministere=Finances
    """
    permission_classes = [IsGovAdmin]

    def get(self, request):
        qs = GovBudgetLine.objects.all()

        annee = request.query_params.get('annee')
        if annee:
            qs = qs.filter(annee=annee)

        ministere = request.query_params.get('ministere')
        if ministere:
            qs = qs.filter(ministere__icontains=ministere)

        serializer = GovBudgetLineSerializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})


class GovContractView(APIView):
    """
    GET /api/v3/foundry/gov/contracts/

    Marchés publics — données mock pour v1.
    La vérification fournisseur via EmPrint-iD se fait en croisant
    `fournisseur_national_id` avec le registre biométrique.
    Filtre : ?statut=ATTRIBUE&ministere=Mines
    """
    permission_classes = [IsGovAdmin]

    def get(self, request):
        qs = GovContract.objects.all()

        statut = request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        ministere = request.query_params.get('ministere')
        if ministere:
            qs = qs.filter(ministere__icontains=ministere)

        serializer = GovContractSerializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})
