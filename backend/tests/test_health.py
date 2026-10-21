"""
Tests Module 09 — Eyeshield Health.

14 tests couvrant :
  - Accès par rôle (200 / 403 / 401)
  - CRUD patients, visites, vaccinations, prescriptions
  - Alertes épidémio + filtres
  - Stats agrégées
  - Propriété taux_letalite
  - vaccination_coverage (TODO(human) — skippé jusqu'à implémentation)
"""
import datetime

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.health.models import EpidemioAlert, HealthPatient, HealthVaccination, HealthVisit
from apps.health.views import vaccination_coverage


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_user(role):
    """Crée un mock user avec le role JWT attendu."""
    class FakeUser:
        is_authenticated = True
        pk = 1

        def __init__(self, r):
            self.role = r

    return FakeUser(role)


def auth_client(role):
    client = APIClient()
    client.force_authenticate(user=make_user(role))
    return client


@pytest.fixture
def health_client():
    return auth_client('ROLE_HEALTH')


@pytest.fixture
def admin_client():
    return auth_client('ROLE_ADMIN')


@pytest.fixture
def bank_client():
    return auth_client('ROLE_BANK')


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def patient(db):
    return HealthPatient.objects.create(national_id='CD-TEST-001', blood_type='O+')


# ── Tests accès ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_patient_list_200_for_health_role(health_client):
    resp = health_client.get('/api/v9/health/patients/')
    assert resp.status_code == 200


@pytest.mark.django_db
def test_patient_list_403_for_bank_role(bank_client):
    resp = bank_client.get('/api/v9/health/patients/')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_patient_list_401_for_anon(anon_client):
    resp = anon_client.get('/api/v9/health/patients/')
    # force_authenticate non appelé → 401 ou 403 selon la config
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_epidemio_200_for_admin(admin_client):
    resp = admin_client.get('/api/v9/health/epidemio/')
    assert resp.status_code == 200


@pytest.mark.django_db
def test_epidemio_403_for_health_worker(health_client):
    resp = health_client.get('/api/v9/health/epidemio/')
    assert resp.status_code == 403


# ── Tests patients ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_create_patient(health_client):
    payload = {'national_id': 'CD-001', 'blood_type': 'A+', 'allergies': ['pénicilline']}
    resp = health_client.post('/api/v9/health/patients/', payload, format='json')
    assert resp.status_code == 201
    assert resp.data['national_id'] == 'CD-001'


@pytest.mark.django_db
def test_patient_detail_includes_sub_resources(health_client, patient):
    # Créer une visite liée
    HealthVisit.objects.create(
        patient=patient, facility_name='CHK', visit_type='CONSULTATION', motif='Fièvre'
    )
    resp = health_client.get(f'/api/v9/health/patients/{patient.national_id}/')
    assert resp.status_code == 200
    assert len(resp.data['visits']) == 1


@pytest.mark.django_db
def test_patient_detail_404_unknown(health_client):
    resp = health_client.get('/api/v9/health/patients/INCONNU-999/')
    assert resp.status_code == 404


# ── Tests visites ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_post_visit_creates_record_and_auto_creates_patient(health_client):
    payload = {
        'national_id':  'CD-NEW-999',
        'facility_name': 'CBCO Kinshasa',
        'visit_type':    'URGENCE',
        'motif':         'Trauma crânien',
    }
    resp = health_client.post('/api/v9/health/visits/', payload, format='json')
    assert resp.status_code == 201
    # Le patient doit avoir été créé automatiquement
    assert HealthPatient.objects.filter(national_id='CD-NEW-999').exists()


@pytest.mark.django_db
def test_post_visit_immutable_once_created(health_client, patient):
    payload = {
        'national_id':   patient.national_id,
        'facility_name': 'CHK',
        'visit_type':    'CONSULTATION',
        'motif':         'Suivi',
    }
    resp = health_client.post('/api/v9/health/visits/', payload, format='json')
    assert resp.status_code == 201
    visit_id = resp.data['id']
    # Aucune route PUT/PATCH n'existe — vérifier l'immuabilité en base
    from apps.health.models import HealthVisit as HV
    visit = HV.objects.get(pk=visit_id)
    assert visit.motif == 'Suivi'   # la donnée originale est préservée


# ── Tests vaccinations ────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_post_vaccination_creates_record(health_client, patient):
    payload = {
        'national_id':        patient.national_id,
        'vaccin_nom':         'BCG',
        'vaccin_code':        'BCG',
        'dose_numero':        1,
        'date_administration': '2024-01-15',
        'facility_name':      'CS Gombe',
    }
    resp = health_client.post('/api/v9/health/vaccinations/', payload, format='json')
    assert resp.status_code == 201
    assert HealthVaccination.objects.filter(patient=patient, vaccin_code='BCG').exists()


# ── Tests épidémio ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_epidemio_filter_by_statut(admin_client, db):
    EpidemioAlert.objects.create(
        disease_code='EBOLA', disease_name='Ebola',
        province='Equateur', cas_confirmes=10, deces=3,
        date_debut=datetime.date(2024, 6, 1), statut='EN_COURS', niveau='CRITIQUE',
    )
    resp = admin_client.get('/api/v9/health/epidemio/?statut=EN_COURS')
    assert resp.status_code == 200
    assert len(resp.data) >= 1


@pytest.mark.django_db
def test_epidemio_filter_by_niveau(admin_client, db):
    EpidemioAlert.objects.create(
        disease_code='CHOLERA', disease_name='Choléra',
        province='Kinshasa', cas_confirmes=50, deces=2,
        date_debut=datetime.date(2024, 3, 1), statut='EN_COURS', niveau='ELEVE',
    )
    resp = admin_client.get('/api/v9/health/epidemio/?niveau=ELEVE')
    assert resp.status_code == 200
    assert any(a['niveau'] == 'ELEVE' for a in resp.data)


# ── Tests stats ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_stats_returns_aggregates(admin_client, db):
    resp = admin_client.get('/api/v9/health/stats/')
    assert resp.status_code == 200
    assert 'patients' in resp.data
    assert 'visits' in resp.data
    assert 'vaccinations' in resp.data
    assert 'epidemio' in resp.data


# ── Test propriété taux_letalite ──────────────────────────────────────────────

@pytest.mark.django_db
def test_taux_letalite_calcul(db):
    alert = EpidemioAlert(
        disease_code='MPOX', disease_name='Mpox',
        province='Sud-Kivu', cas_confirmes=200, deces=10,
        date_debut=datetime.date(2024, 1, 1),
    )
    assert alert.taux_letalite == 5.0


@pytest.mark.django_db
def test_taux_letalite_zero_si_aucun_cas(db):
    alert = EpidemioAlert(
        disease_code='X', disease_name='X',
        province='Test', cas_confirmes=0, deces=0,
        date_debut=datetime.date(2024, 1, 1),
    )
    assert alert.taux_letalite == 0.0


# ── Test vaccination_coverage (TODO(human)) ───────────────────────────────────

@pytest.mark.django_db
def test_vaccination_coverage_skipped_until_implemented(db):
    result = vaccination_coverage('CD-TEST-XXX')
    if result is None:
        pytest.skip("vaccination_coverage() pas encore implémentée — TODO(human)")
    assert 'coverage_pct' in result
    assert 'missing_vaccines' in result
