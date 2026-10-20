"""
Tests Foundry Health — dossier patient unifié + épidémiologie.

Couvre :
  - HealthPatientListView  : liste + filtres
  - HealthPatientDetailView: dossier complet (visites + vaccins + ordonnances)
  - HealthVisitView        : POST visite (auto-crée le patient si absent)
  - HealthVaccinationView  : POST vaccination
  - EpidemioAlertView      : dashboard épidémio + filtres
  - HealthStatsView        : statistiques agrégées
  - RBAC                   : ROLE_HEALTH (worker), ROLE_ADMIN, ROLE_BANK (bloqué)
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.foundry.models import (
    HealthPatient, HealthVisit, HealthVaccination, EpidemioAlert,
    SectorTenant,
)

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_for_role(role: str) -> APIClient:
    """Crée un APIClient authentifié avec le rôle JWT donné."""
    user = User.objects.create_user(f'health_{uuid.uuid4().hex[:6]}', password='pw')
    token = AccessToken.for_user(user)
    token['role'] = role
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
    client._user = user  # stocker pour les vues qui lisent request.user
    return client


def _make_facility(**kwargs) -> SectorTenant:
    """Crée un SectorTenant HEALTH en base."""
    defaults = dict(name=f"HGK-{uuid.uuid4().hex[:4]}", sector='HEALTH')
    defaults.update(kwargs)
    return SectorTenant.objects.create(**defaults)


def _make_patient(national_id=None, **kwargs) -> HealthPatient:
    """Crée un HealthPatient en base."""
    defaults = dict(
        national_id=national_id or f"CD{uuid.uuid4().hex[:8].upper()}",
        blood_type='O+',
    )
    defaults.update(kwargs)
    return HealthPatient.objects.create(**defaults)


def _make_epidemio(**kwargs) -> EpidemioAlert:
    """Crée une EpidemioAlert en base."""
    defaults = dict(
        disease_code='A00',
        disease_name='Choléra',
        province='Kivu',
        cas_confirmes=50,
        cas_suspects=120,
        deces=5,
        date_debut=date(2026, 1, 1),
        niveau=EpidemioAlert.Niveau.ELEVE,
        statut=EpidemioAlert.Statut.EN_COURS,
        source='OMS',
    )
    defaults.update(kwargs)
    return EpidemioAlert.objects.create(**defaults)


# ── Patient List ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_patient_list_200_for_health_role():
    """ROLE_HEALTH peut lister les patients."""
    _make_patient()
    client = _client_for_role('ROLE_HEALTH')
    response = client.get('/api/v3/foundry/health/patients/')
    assert response.status_code == 200
    assert response.data['count'] >= 1


@pytest.mark.django_db
def test_patient_list_403_for_bank_role():
    """ROLE_BANK est bloqué (secteurs séparés)."""
    client = _client_for_role('ROLE_BANK')
    response = client.get('/api/v3/foundry/health/patients/')
    assert response.status_code == 403


@pytest.mark.django_db
def test_patient_list_401_for_anon():
    """Anonyme → 401."""
    response = APIClient().get('/api/v3/foundry/health/patients/')
    assert response.status_code == 401


@pytest.mark.django_db
def test_patient_list_filter_by_blood_type():
    """Le filtre ?blood_type= ne retourne que les patients du groupe concerné."""
    _make_patient(blood_type='A+')
    _make_patient(blood_type='O-')

    client = _client_for_role('ROLE_HEALTH')
    response = client.get('/api/v3/foundry/health/patients/', {'blood_type': 'A+'})

    assert response.status_code == 200
    for patient in response.data['results']:
        assert patient['blood_type'] == 'A+'


# ── Patient Detail ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_patient_detail_includes_visits_vaccinations_prescriptions():
    """Le dossier détail inclut les visites, vaccinations et prescriptions."""
    facility = _make_facility()
    patient  = _make_patient()

    # Créer une visite
    HealthVisit.objects.create(
        patient=patient, facility=facility, agent=None,
        type_visite=HealthVisit.TypeVisite.CONSULTATION,
        motif="Fièvre persistante",
    )

    # Créer une vaccination
    HealthVaccination.objects.create(
        patient=patient, facility=facility, agent=None,
        vaccin_nom="BCG", vaccin_code="BCG",
        dose_numero=1, date_administration=date(2026, 1, 15),
    )

    client = _client_for_role('ROLE_HEALTH')
    response = client.get(f'/api/v3/foundry/health/patients/{patient.national_id}/')

    assert response.status_code == 200
    assert len(response.data['visits']) == 1
    assert response.data['visits'][0]['motif'] == 'Fièvre persistante'
    assert len(response.data['vaccinations']) == 1
    assert response.data['vaccinations'][0]['vaccin_code'] == 'BCG'
    assert 'prescriptions' in response.data


@pytest.mark.django_db
def test_patient_detail_404_unknown_national_id():
    """ID inconnu → 404."""
    client = _client_for_role('ROLE_HEALTH')
    response = client.get('/api/v3/foundry/health/patients/INCONNU999/')
    assert response.status_code == 404


# ── POST Visit ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_post_visit_creates_record_and_patient():
    """POST /visits/ crée la visite ET le patient si absent."""
    facility = _make_facility()
    national_id = f"CD{uuid.uuid4().hex[:8].upper()}"

    client = _client_for_role('ROLE_HEALTH')
    response = client.post('/api/v3/foundry/health/visits/', {
        'patient_national_id': national_id,
        'facility_id':         str(facility.id),
        'type_visite':         'URGENCE',
        'motif':               'Accident de la route',
    }, format='json')

    assert response.status_code == 201
    assert response.data['type_visite'] == 'URGENCE'
    assert response.data['motif'] == 'Accident de la route'
    # Le dossier patient a été créé automatiquement
    assert HealthPatient.objects.filter(national_id=national_id).exists()


@pytest.mark.django_db
def test_post_visit_invalid_facility_returns_400():
    """POST avec un facility_id inconnu → 400."""
    client = _client_for_role('ROLE_HEALTH')
    response = client.post('/api/v3/foundry/health/visits/', {
        'patient_national_id': 'CD123456',
        'facility_id':         str(uuid.uuid4()),   # UUID inexistant
        'type_visite':         'CONSULTATION',
        'motif':               'Test',
    }, format='json')
    assert response.status_code == 400


# ── POST Vaccination ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_post_vaccination_creates_record():
    """POST /vaccinations/ enregistre une vaccination."""
    facility = _make_facility()
    patient  = _make_patient()

    client = _client_for_role('ROLE_HEALTH')
    response = client.post('/api/v3/foundry/health/vaccinations/', {
        'patient_national_id': patient.national_id,
        'facility_id':         str(facility.id),
        'vaccin_nom':          'Vaccin polio oral',
        'vaccin_code':         'OPV',
        'dose_numero':         2,
        'date_administration': '2026-03-01',
    }, format='json')

    assert response.status_code == 201
    assert response.data['vaccin_code'] == 'OPV'
    assert response.data['dose_numero'] == 2


@pytest.mark.django_db
def test_post_vaccination_unknown_patient_returns_400():
    """POST vaccination pour un patient sans dossier → 400."""
    facility = _make_facility()
    client   = _client_for_role('ROLE_HEALTH')
    response = client.post('/api/v3/foundry/health/vaccinations/', {
        'patient_national_id': 'INCONNU_TOTAL',
        'facility_id':         str(facility.id),
        'vaccin_nom':          'BCG',
        'vaccin_code':         'BCG',
        'dose_numero':         1,
        'date_administration': '2026-03-01',
    }, format='json')
    assert response.status_code == 400


# ── Épidémiologie ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_epidemio_200_for_admin():
    """ROLE_ADMIN peut accéder au dashboard épidémio."""
    _make_epidemio()
    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/foundry/health/epidemio/')
    assert response.status_code == 200
    assert response.data['count'] >= 1


@pytest.mark.django_db
def test_epidemio_403_for_health_worker():
    """ROLE_HEALTH ne peut pas accéder au dashboard épidémio (admin seulement)."""
    client = _client_for_role('ROLE_HEALTH')
    response = client.get('/api/v3/foundry/health/epidemio/')
    assert response.status_code == 403


@pytest.mark.django_db
def test_epidemio_filter_by_statut():
    """Le filtre ?statut= ne retourne que les alertes du statut demandé."""
    _make_epidemio(statut=EpidemioAlert.Statut.EN_COURS)
    _make_epidemio(statut=EpidemioAlert.Statut.RESOLU, disease_name='Rougeole', province='Kinshasa')

    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/foundry/health/epidemio/', {'statut': 'EN_COURS'})

    assert response.status_code == 200
    for alert in response.data['results']:
        assert alert['statut'] == 'EN_COURS'


@pytest.mark.django_db
def test_epidemio_filter_by_niveau():
    """Le filtre ?niveau= filtre par niveau de criticité."""
    _make_epidemio(niveau=EpidemioAlert.Niveau.CRITIQUE, disease_name='Ebola', province='Ituri')
    _make_epidemio(niveau=EpidemioAlert.Niveau.FAIBLE, disease_name='Grippe', province='Kongo Central')

    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/foundry/health/epidemio/', {'niveau': 'CRITIQUE'})

    assert response.status_code == 200
    assert response.data['count'] >= 1
    for alert in response.data['results']:
        assert alert['niveau'] == 'CRITIQUE'


# ── Stats ─────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_stats_returns_aggregates():
    """HealthStatsView retourne les compteurs agrégés."""
    facility = _make_facility()
    p1 = _make_patient()
    p2 = _make_patient()

    HealthVisit.objects.create(patient=p1, facility=facility, agent=None,
                               type_visite='CONSULTATION', motif='Fièvre')
    HealthVisit.objects.create(patient=p2, facility=facility, agent=None,
                               type_visite='URGENCE', motif='Blessure')

    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/foundry/health/stats/')

    assert response.status_code == 200
    assert response.data['total_patients'] >= 2
    assert response.data['total_visits'] >= 2
    assert 'visits_by_type' in response.data
    assert 'top_diagnostics' in response.data


# ── taux_letalite ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_taux_letalite_calcul():
    """taux_letalite = deces / cas_confirmes × 100."""
    alert = _make_epidemio(cas_confirmes=100, deces=10)
    assert alert.taux_letalite == pytest.approx(10.0, abs=0.01)


@pytest.mark.django_db
def test_taux_letalite_zero_cas():
    """taux_letalite vaut 0.0 si cas_confirmes = 0 (évite la division par zéro)."""
    alert = _make_epidemio(cas_confirmes=0, deces=0)
    assert alert.taux_letalite == 0.0
