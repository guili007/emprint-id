"""
Tests Module 08 — Eyeshield Justice.

Couvre :
  - CriminalRecordListCreateView : liste, filtres, POST création
  - CriminalProfileView          : profil complet 200/404-like, mandats+alertes inclus
  - ArrestWarrantListCreateView  : liste, filtres, POST
  - ArrestWarrantStatusView      : PATCH transitions, 409 si déjà exécuté
  - JusticeAlertListCreateView   : liste, filtres, POST
  - JusticeStatsView             : structure de la réponse
  - recidivism_risk              : score de récidive (une fois implémenté)
  - RBAC : ROLE_INTEL OK écriture, ROLE_POLICE lecture, ROLE_BANK 403, anonyme 401
"""
import uuid
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.justice.models import ArrestWarrant, CriminalRecord, JusticeAlert
from apps.justice.views import recidivism_risk

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_for_role(role: str):
    user = User.objects.create_user(f'jus_{uuid.uuid4().hex[:6]}', password='pw')
    token = AccessToken.for_user(user)
    token['role'] = role
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
    return client, user


def _make_record(national_id='CD-JUST-001', record_type='MISDEMEANOR', **kwargs) -> CriminalRecord:
    defaults = dict(
        national_id=national_id,
        record_type=record_type,
        offense_code='P-221',
        offense_description='Vol simple',
        judgment_date=date(2024, 3, 15),
        court_name='TGI Kinshasa',
        sentence_type='PRISON',
        sentence_duration_months=6,
    )
    defaults.update(kwargs)
    return CriminalRecord.objects.create(**defaults)


def _make_warrant(national_id='CD-JUST-001', **kwargs) -> ArrestWarrant:
    defaults = dict(
        national_id=national_id,
        warrant_type='ARREST',
        issued_by='Parquet de Kinshasa',
        offense_description='Suspicion de fraude',
        status='ACTIVE',
    )
    defaults.update(kwargs)
    return ArrestWarrant.objects.create(**defaults)


def _make_alert(national_id='CD-JUST-001', **kwargs) -> JusticeAlert:
    defaults = dict(
        national_id=national_id,
        alert_type='WANTED',
        severity='HIGH',
        title='Individu recherché',
        description='Fugitif après condamnation',
        status='ACTIVE',
    )
    defaults.update(kwargs)
    return JusticeAlert.objects.create(**defaults)


# ── Casier judiciaire ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_record_list_200_for_police():
    client, _ = _client_for_role('ROLE_POLICE')
    _make_record()
    r = client.get('/api/v8/justice/records/')
    assert r.status_code == 200
    assert isinstance(r.data, list)


@pytest.mark.django_db
def test_record_list_403_for_bank():
    client, _ = _client_for_role('ROLE_BANK')
    r = client.get('/api/v8/justice/records/')
    assert r.status_code == 403


@pytest.mark.django_db
def test_record_list_401_for_anon():
    r = APIClient().get('/api/v8/justice/records/')
    assert r.status_code == 401


@pytest.mark.django_db
def test_record_list_filter_by_national_id():
    client, _ = _client_for_role('ROLE_INTEL')
    _make_record(national_id='CD-TARGET-001')
    _make_record(national_id='CD-OTHER-002')
    r = client.get('/api/v8/justice/records/?national_id=CD-TARGET-001')
    assert r.status_code == 200
    assert all(rec['national_id'] == 'CD-TARGET-001' for rec in r.data)


@pytest.mark.django_db
def test_record_create_201_for_intel():
    client, _ = _client_for_role('ROLE_INTEL')
    r = client.post('/api/v8/justice/records/', {
        'national_id': 'CD-NEW-001',
        'record_type': 'FELONY',
        'offense_description': 'Meurtre',
        'judgment_date': '2026-01-10',
        'court_name': 'Cour Suprême',
        'sentence_type': 'PRISON',
        'sentence_duration_months': 120,
    }, format='json')
    assert r.status_code == 201
    assert r.data['national_id'] == 'CD-NEW-001'


@pytest.mark.django_db
def test_record_create_403_for_police():
    client, _ = _client_for_role('ROLE_POLICE')
    r = client.post('/api/v8/justice/records/', {}, format='json')
    assert r.status_code == 403


# ── Profil pénal ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_profile_200_with_records_warrants_alerts():
    client, _ = _client_for_role('ROLE_INTEL')
    nid = 'CD-PROFILE-001'
    _make_record(national_id=nid)
    _make_warrant(national_id=nid)
    _make_alert(national_id=nid)
    r = client.get(f'/api/v8/justice/records/{nid}/profile/')
    assert r.status_code == 200
    assert r.data['national_id'] == nid
    assert len(r.data['records']) >= 1
    assert len(r.data['active_warrants']) >= 1
    assert len(r.data['active_alerts']) >= 1
    assert 'recidivism_risk' in r.data


@pytest.mark.django_db
def test_profile_empty_citizen_returns_200():
    client, _ = _client_for_role('ROLE_POLICE')
    r = client.get('/api/v8/justice/records/CD-CLEAN-999/profile/')
    assert r.status_code == 200
    assert r.data['records'] == []
    assert r.data['active_warrants'] == []


# ── Mandats ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_warrant_list_200_for_border():
    client, _ = _client_for_role('ROLE_BORDER')
    _make_warrant()
    r = client.get('/api/v8/justice/warrants/')
    assert r.status_code == 200
    assert len(r.data) >= 1


@pytest.mark.django_db
def test_warrant_create_201_for_intel():
    client, _ = _client_for_role('ROLE_INTEL')
    r = client.post('/api/v8/justice/warrants/', {
        'national_id': 'CD-WARRANT-001',
        'warrant_type': 'ARREST',
        'issued_by': 'Parquet Lubumbashi',
        'offense_description': 'Suspicion trafic armes',
    }, format='json')
    assert r.status_code == 201
    assert r.data['status'] == 'ACTIVE'


@pytest.mark.django_db
def test_warrant_status_active_to_executed():
    client, _ = _client_for_role('ROLE_INTEL')
    warrant = _make_warrant()
    r = client.patch(f'/api/v8/justice/warrants/{warrant.pk}/status/', {'status': 'EXECUTED'})
    assert r.status_code == 200
    assert r.data['status'] == 'EXECUTED'
    assert r.data['executed_at'] is not None


@pytest.mark.django_db
def test_warrant_status_already_executed_returns_409():
    client, _ = _client_for_role('ROLE_ADMIN')
    warrant = _make_warrant(status='EXECUTED')
    r = client.patch(f'/api/v8/justice/warrants/{warrant.pk}/status/', {'status': 'CANCELLED'})
    assert r.status_code == 409


# ── Alertes ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_alert_list_200_for_intel():
    client, _ = _client_for_role('ROLE_INTEL')
    _make_alert()
    r = client.get('/api/v8/justice/alerts/')
    assert r.status_code == 200


@pytest.mark.django_db
def test_alert_list_filter_by_severity():
    client, _ = _client_for_role('ROLE_POLICE')
    _make_alert(severity='CRITICAL')
    _make_alert(severity='LOW')
    r = client.get('/api/v8/justice/alerts/?severity=CRITICAL')
    assert r.status_code == 200
    assert all(a['severity'] == 'CRITICAL' for a in r.data)


@pytest.mark.django_db
def test_alert_create_201_for_admin():
    client, _ = _client_for_role('ROLE_ADMIN')
    r = client.post('/api/v8/justice/alerts/', {
        'national_id': 'CD-ALERT-001',
        'alert_type': 'INTERNATIONAL_WANTED',
        'severity': 'CRITICAL',
        'title': 'Fugitif Interpol',
        'description': 'Notice rouge émise',
    }, format='json')
    assert r.status_code == 201


# ── Stats ─────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_stats_200_for_police():
    client, _ = _client_for_role('ROLE_POLICE')
    r = client.get('/api/v8/justice/stats/')
    assert r.status_code == 200
    assert 'criminal_records' in r.data
    assert 'warrants' in r.data
    assert 'alerts' in r.data


@pytest.mark.django_db
def test_stats_403_for_bank():
    client, _ = _client_for_role('ROLE_BANK')
    r = client.get('/api/v8/justice/stats/')
    assert r.status_code == 403


# ── recidivism_risk ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_recidivism_risk_low_for_clean_citizen():
    """Citoyen sans casier → risque LOW."""
    result = recidivism_risk('CD-CLEAN-000')
    if result is None:
        pytest.skip("recidivism_risk pas encore implémenté")
    assert result['level'] == 'LOW'
    assert result['conviction_count'] == 0
    assert result['has_felony'] is False


@pytest.mark.django_db
def test_recidivism_risk_high_for_felony():
    """Un seul FELONY → niveau minimum HIGH."""
    _make_record(national_id='CD-FELON-001', record_type='FELONY')
    result = recidivism_risk('CD-FELON-001')
    if result is None:
        pytest.skip("recidivism_risk pas encore implémenté")
    assert result['has_felony'] is True
    assert result['level'] in ('HIGH', 'CRITICAL')


@pytest.mark.django_db
def test_recidivism_risk_acquittal_not_counted():
    """Un acquittement seul ne doit pas augmenter le score."""
    _make_record(national_id='CD-ACQUIT-001', record_type='ACQUITTAL', sentence_type='ACQUITTED')
    result = recidivism_risk('CD-ACQUIT-001')
    if result is None:
        pytest.skip("recidivism_risk pas encore implémenté")
    assert result['conviction_count'] == 0
    assert result['level'] == 'LOW'
