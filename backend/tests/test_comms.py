"""
Tests Module 06 — Eyeshield Comms.

Couvre :
  - SimCardListCreateView : liste, filtres, POST création
  - SimCardProfileView    : profil complet citoyen, 404 inconnu
  - CallRecordListCreateView : liste, filtres msisdn/type, POST CDR
  - CommsAlertListCreateView : liste, filtres, POST alerte manuelle
  - CommsStatsView        : structure de la réponse
  - severity_for_imei_swap : logique sévérité (une fois implémentée)
  - RBAC : ROLE_INTEL OK, ROLE_BANK 403, ROLE_POLICE lecture seule, anonyme 401
"""
import uuid
from datetime import datetime, timezone as dt_tz

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.comms.models import CallRecord, CommsAlert, SimCard

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_for_role(role: str):
    user = User.objects.create_user(f'comms_{uuid.uuid4().hex[:6]}', password='pw')
    token = AccessToken.for_user(user)
    token['role'] = role
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
    return client, user


def _make_sim(**kwargs) -> SimCard:
    defaults = dict(
        msisdn=f'+243{uuid.uuid4().int % 900000000 + 100000000}',
        imei='352099001761481',
        national_id='CD-COMMS-001',
        operator='MTN',
        status='ACTIVE',
    )
    defaults.update(kwargs)
    return SimCard.objects.create(**defaults)


def _make_record(**kwargs) -> CallRecord:
    defaults = dict(
        caller_msisdn='+243810000001',
        callee_msisdn='+243810000002',
        call_type='VOICE',
        duration_sec=120,
        started_at=datetime(2026, 10, 20, 14, 0, tzinfo=dt_tz.utc),
    )
    defaults.update(kwargs)
    return CallRecord.objects.create(**defaults)


def _make_alert(**kwargs) -> CommsAlert:
    defaults = dict(
        alert_type='IMEI_SWAP',
        severity='HIGH',
        national_id='CD-COMMS-001',
        msisdn_a='+243810000001',
        title='Swap IMEI suspect',
        status='OPEN',
    )
    defaults.update(kwargs)
    return CommsAlert.objects.create(**defaults)


# ── SimCardListCreateView ─────────────────────────────────────────────────────

@pytest.mark.django_db
def test_sim_list_200_for_intel():
    client, _ = _client_for_role('ROLE_INTEL')
    _make_sim()
    r = client.get('/api/v6/comms/sims/')
    assert r.status_code == 200
    assert len(r.data) >= 1


@pytest.mark.django_db
def test_sim_list_403_for_bank():
    client, _ = _client_for_role('ROLE_BANK')
    r = client.get('/api/v6/comms/sims/')
    assert r.status_code == 403


@pytest.mark.django_db
def test_sim_list_401_for_anon():
    r = APIClient().get('/api/v6/comms/sims/')
    assert r.status_code == 401


@pytest.mark.django_db
def test_sim_list_filter_by_national_id():
    client, _ = _client_for_role('ROLE_INTEL')
    _make_sim(national_id='CD-AAA-001')
    _make_sim(national_id='CD-BBB-002')
    r = client.get('/api/v6/comms/sims/?national_id=CD-AAA-001')
    assert r.status_code == 200
    assert all(s['national_id'] == 'CD-AAA-001' for s in r.data)


@pytest.mark.django_db
def test_sim_list_filter_by_operator():
    client, _ = _client_for_role('ROLE_POLICE')
    _make_sim(operator='MTN')
    _make_sim(operator='AIRTEL')
    r = client.get('/api/v6/comms/sims/?operator=MTN')
    assert r.status_code == 200
    assert all(s['operator'] == 'MTN' for s in r.data)


@pytest.mark.django_db
def test_sim_create_201_for_intel():
    client, _ = _client_for_role('ROLE_INTEL')
    payload = {
        'msisdn':      '+243815550001',
        'imei':        '352099001761481',
        'national_id': 'CD-NEW-001',
        'operator':    'VODACOM',
        'status':      'ACTIVE',
    }
    r = client.post('/api/v6/comms/sims/', payload)
    assert r.status_code == 201
    assert r.data['msisdn'] == '+243815550001'


@pytest.mark.django_db
def test_sim_create_403_for_police():
    # ROLE_POLICE = lecture seule, pas d'écriture
    client, _ = _client_for_role('ROLE_POLICE')
    r = client.post('/api/v6/comms/sims/', {'msisdn': '+243815550002', 'operator': 'MTN'})
    assert r.status_code == 403


# ── SimCardProfileView ────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_sim_profile_200():
    client, _ = _client_for_role('ROLE_INTEL')
    _make_sim(national_id='CD-PROF-001')
    r = client.get('/api/v6/comms/sims/CD-PROF-001/profile/')
    assert r.status_code == 200
    assert r.data['national_id'] == 'CD-PROF-001'
    assert r.data['sim_count'] >= 1
    assert 'known_imeis' in r.data
    assert 'recent_records' in r.data


@pytest.mark.django_db
def test_sim_profile_404_unknown():
    client, _ = _client_for_role('ROLE_INTEL')
    r = client.get('/api/v6/comms/sims/CD-INEX-999/profile/')
    assert r.status_code == 404


# ── CallRecordListCreateView ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_call_record_list_200():
    client, _ = _client_for_role('ROLE_POLICE')
    _make_record()
    r = client.get('/api/v6/comms/records/')
    assert r.status_code == 200
    assert len(r.data) >= 1


@pytest.mark.django_db
def test_call_record_list_filter_by_msisdn():
    client, _ = _client_for_role('ROLE_INTEL')
    _make_record(caller_msisdn='+243810000010')
    _make_record(caller_msisdn='+243810000099')
    r = client.get('/api/v6/comms/records/?msisdn=%2B243810000010')
    assert r.status_code == 200
    assert all(
        rec['caller_msisdn'] == '+243810000010' or rec['callee_msisdn'] == '+243810000010'
        for rec in r.data
    )


@pytest.mark.django_db
def test_call_record_create_201():
    client, _ = _client_for_role('ROLE_INTEL')
    payload = {
        'caller_msisdn': '+243810000020',
        'callee_msisdn': '+243810000021',
        'call_type':     'SMS',
        'duration_sec':  0,
        'started_at':    '2026-10-20T10:00:00Z',
    }
    r = client.post('/api/v6/comms/records/', payload)
    assert r.status_code == 201
    assert r.data['call_type'] == 'SMS'


# ── CommsAlertListCreateView ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_comms_alert_list_200():
    client, _ = _client_for_role('ROLE_BORDER')
    _make_alert()
    r = client.get('/api/v6/comms/alerts/')
    assert r.status_code == 200
    assert len(r.data) >= 1


@pytest.mark.django_db
def test_comms_alert_list_filter_by_type():
    client, _ = _client_for_role('ROLE_INTEL')
    _make_alert(alert_type='IMEI_SWAP')
    _make_alert(alert_type='MULTI_SIM')
    r = client.get('/api/v6/comms/alerts/?alert_type=IMEI_SWAP')
    assert r.status_code == 200
    assert all(a['alert_type'] == 'IMEI_SWAP' for a in r.data)


@pytest.mark.django_db
def test_comms_alert_create_201():
    client, _ = _client_for_role('ROLE_INTEL')
    payload = {
        'alert_type':  'MULTI_SIM',
        'severity':    'MEDIUM',
        'national_id': 'CD-COMMS-002',
        'msisdn_a':    '+243820000001',
        'title':       'Multi-SIM détecté',
        'description': 'Trois SIMs actives pour le même citoyen',
    }
    r = client.post('/api/v6/comms/alerts/', payload)
    assert r.status_code == 201
    assert r.data['alert_type'] == 'MULTI_SIM'


# ── CommsStatsView ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_comms_stats_200():
    client, _ = _client_for_role('ROLE_ADMIN')
    r = client.get('/api/v6/comms/stats/')
    assert r.status_code == 200
    assert 'sims' in r.data
    assert 'call_records' in r.data
    assert 'alerts' in r.data


@pytest.mark.django_db
def test_comms_stats_403_for_health():
    client, _ = _client_for_role('ROLE_HEALTH')
    r = client.get('/api/v6/comms/stats/')
    assert r.status_code == 403


# ── severity_for_imei_swap ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_severity_for_imei_swap_low_for_one():
    from apps.comms.views import severity_for_imei_swap
    if severity_for_imei_swap(1) is None:
        pytest.skip("TODO(human) pas encore implémenté")
    assert severity_for_imei_swap(1) == 'LOW'


@pytest.mark.django_db
def test_severity_for_imei_swap_critical_for_many():
    from apps.comms.views import severity_for_imei_swap
    if severity_for_imei_swap(10) is None:
        pytest.skip("TODO(human) pas encore implémenté")
    assert severity_for_imei_swap(10) == 'CRITICAL'
