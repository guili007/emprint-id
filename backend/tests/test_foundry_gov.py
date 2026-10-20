"""
Tests Foundry Gov — dashboard opérationnel Ministères.

Couvre :
  - GovEmployeeListView  : liste + filtres ?statut=, ?administration=, ?q=
  - GovEmployeeDetailView: détail + carrière
  - GovStatsView         : statistiques agrégées
  - GovBudgetView        : lignes budgétaires mock
  - GovContractView      : marchés publics mock
  - RBAC                 : ROLE_GOV, ROLE_ADMIN, ROLE_BANK (doit être bloqué)

Stratégie auth : JWT réel (AccessToken.for_user + claim 'role') via APIClient,
exactement comme test_foundry.py — cohérence avec RoleJWTAuthentication.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.foundry.models import (
    GovEmployee, GovCareerEvent, GovBudgetLine, GovContract,
)

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_for_role(role: str) -> APIClient:
    """Crée un APIClient authentifié avec le rôle JWT donné."""
    user = User.objects.create_user(f'gov_agent_{uuid.uuid4().hex[:6]}', password='pw')
    token = AccessToken.for_user(user)
    token['role'] = role
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
    return client


def _make_employee(**kwargs) -> GovEmployee:
    """Crée un GovEmployee en base avec des valeurs par défaut."""
    defaults = dict(
        siga_uuid=uuid.uuid4(),
        matricule=f"MAT{uuid.uuid4().hex[:6].upper()}",
        nom="Kabila",
        postnom="Jean",
        prenom="Pierre",
        statut=GovEmployee.Statut.ACTIF,
        administration_nom="Ministère des Finances",
        synced_at=None,
    )
    defaults.update(kwargs)
    return GovEmployee.objects.create(**defaults)


# ── Employee List ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_employee_list_returns_200_for_gov_role():
    """ROLE_GOV peut lister les fonctionnaires."""
    _make_employee()
    client = _client_for_role('ROLE_GOV')
    response = client.get('/api/v3/foundry/gov/employees/')
    assert response.status_code == 200
    assert response.data['count'] >= 1


@pytest.mark.django_db
def test_employee_list_blocked_for_bank_role():
    """ROLE_BANK ne doit pas accéder au Gov (secteurs séparés)."""
    client = _client_for_role('ROLE_BANK')
    response = client.get('/api/v3/foundry/gov/employees/')
    assert response.status_code == 403


@pytest.mark.django_db
def test_employee_list_anon_returns_401():
    """Anonyme → 401."""
    response = APIClient().get('/api/v3/foundry/gov/employees/')
    assert response.status_code == 401


@pytest.mark.django_db
def test_employee_list_filter_by_statut():
    """Le filtre ?statut=RETRAITE n'affiche que les retraités."""
    _make_employee(statut=GovEmployee.Statut.ACTIF)
    _make_employee(statut=GovEmployee.Statut.RETRAITE)

    client = _client_for_role('ROLE_GOV')
    response = client.get('/api/v3/foundry/gov/employees/', {'statut': 'RETRAITE'})

    assert response.status_code == 200
    for emp in response.data['results']:
        assert emp['statut'] == 'RETRAITE'


@pytest.mark.django_db
def test_employee_list_filter_by_administration():
    """Le filtre ?administration= fait un icontains sur le nom de ministère."""
    _make_employee(administration_nom="Ministère des Mines")
    _make_employee(administration_nom="Ministère de la Santé")

    client = _client_for_role('ROLE_GOV')
    response = client.get('/api/v3/foundry/gov/employees/', {'administration': 'Mines'})

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert 'Mines' in response.data['results'][0]['administration_nom']


@pytest.mark.django_db
def test_employee_list_search_by_nom():
    """Le paramètre ?q= cherche dans nom, postnom et matricule."""
    _make_employee(nom="Mutombo", matricule="MATMUT001")
    _make_employee(nom="Kabila",  matricule="MATKAB001")

    client = _client_for_role('ROLE_GOV')
    response = client.get('/api/v3/foundry/gov/employees/', {'q': 'Mutombo'})

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['nom'] == 'Mutombo'


# ── Employee Detail ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_employee_detail_returns_career_events():
    """Le détail inclut les événements de carrière."""
    emp = _make_employee()
    GovCareerEvent.objects.create(
        employee=emp,
        type_evenement=GovCareerEvent.TypeEvenement.PROMOTION,
        date_effet=date(2022, 1, 1),
        reference_acte="ACTE/2022/001",
    )

    client = _client_for_role('ROLE_GOV')
    response = client.get(f'/api/v3/foundry/gov/employees/{emp.siga_uuid}/')

    assert response.status_code == 200
    assert len(response.data['career_events']) == 1
    assert response.data['career_events'][0]['type_evenement'] == 'PROMOTION'


@pytest.mark.django_db
def test_employee_detail_404_for_unknown_uuid():
    """UUID inexistant → 404."""
    client = _client_for_role('ROLE_GOV')
    response = client.get(f'/api/v3/foundry/gov/employees/{uuid.uuid4()}/')
    assert response.status_code == 404


# ── Stats ─────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_stats_returns_correct_counts():
    """GovStatsView retourne le total et le décompte par statut."""
    _make_employee(statut=GovEmployee.Statut.ACTIF)
    _make_employee(statut=GovEmployee.Statut.ACTIF)
    _make_employee(statut=GovEmployee.Statut.RETRAITE)

    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/foundry/gov/stats/')

    assert response.status_code == 200
    assert response.data['total_employees'] >= 3
    assert response.data['actifs'] >= 2
    assert response.data['retraites'] >= 1


@pytest.mark.django_db
def test_stats_blocked_for_gov_reader():
    """ROLE_GOV n'a pas accès aux stats (réservé ROLE_ADMIN)."""
    client = _client_for_role('ROLE_GOV')
    response = client.get('/api/v3/foundry/gov/stats/')
    assert response.status_code == 403


# ── Budget ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_budget_returns_results():
    """GovBudgetView retourne les lignes budgétaires."""
    GovBudgetLine.objects.create(
        annee=2026,
        ministere="Finances",
        poste_budgetaire="Rémunérations",
        montant_alloue=Decimal("1000000.00"),
        montant_execute=Decimal("750000.00"),
    )

    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/foundry/gov/budget/')

    assert response.status_code == 200
    assert response.data['count'] >= 1
    # taux_execution doit être présent dans la sérialisation
    assert 'taux_execution' in response.data['results'][0]


@pytest.mark.django_db
def test_budget_taux_execution_calcul():
    """taux_execution = (exécuté / alloué) × 100."""
    GovBudgetLine.objects.create(
        annee=2026,
        ministere="Mines",
        poste_budgetaire="Investissements",
        montant_alloue=Decimal("200000.00"),
        montant_execute=Decimal("100000.00"),
    )

    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/foundry/gov/budget/', {'ministere': 'Mines'})

    assert response.status_code == 200
    assert pytest.approx(response.data['results'][0]['taux_execution'], abs=0.1) == 50.0


# ── Contracts ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_contracts_returns_results():
    """GovContractView retourne les marchés publics."""
    GovContract.objects.create(
        reference="REF/2026/001",
        objet="Construction route Goma-Rutshuru",
        fournisseur_nom="GTCL SARL",
        montant=Decimal("5000000.00"),
        ministere="Travaux Publics",
        statut=GovContract.Statut.ATTRIBUE,
    )

    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/foundry/gov/contracts/')

    assert response.status_code == 200
    assert response.data['count'] >= 1
    assert response.data['results'][0]['reference'] == 'REF/2026/001'


@pytest.mark.django_db
def test_contracts_filter_by_statut():
    """Le filtre ?statut= ne retourne que les marchés du statut demandé."""
    GovContract.objects.create(
        reference="REF/2026/002",
        objet="Fourniture matériel médical",
        fournisseur_nom="MedCo",
        montant=Decimal("80000.00"),
        ministere="Santé",
        statut=GovContract.Statut.EN_COURS,
    )
    GovContract.objects.create(
        reference="REF/2026/003",
        objet="Audit IT",
        fournisseur_nom="TechAudit",
        montant=Decimal("20000.00"),
        ministere="Numérique",
        statut=GovContract.Statut.ATTRIBUE,
    )

    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/foundry/gov/contracts/', {'statut': 'EN_COURS'})

    assert response.status_code == 200
    for contract in response.data['results']:
        assert contract['statut'] == 'EN_COURS'
