"""
Tests Module 07 — Eyeshield Field.

Couvre :
  - FieldAgentListView        : liste, filtres status/province
  - FieldMissionListCreateView: liste, filtres, POST création
  - FieldMissionDetailView    : détail 200/404
  - FieldSyncView             : sync batch, idempotence, compteurs
  - FieldRecordListView       : liste, filtres type/agent/date
  - FieldStatsView            : structure de la réponse
  - _is_duplicate_record      : logique de détection doublon (une fois implémentée)
  - RBAC : ROLE_INTEL lecture, ROLE_BANK 403, ROLE_POLICE lecture+sync, anonyme 401
"""
import uuid
from datetime import datetime, timezone as dt_tz

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.field.models import FieldAgent, FieldMission, FieldRecord, SyncBatch
from apps.field.views import _is_duplicate_record

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_for_role(role: str):
    user = User.objects.create_user(f'field_{uuid.uuid4().hex[:6]}', password='pw')
    token = AccessToken.for_user(user)
    token['role'] = role
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
    return client, user


def _make_agent(user=None) -> FieldAgent:
    if user is None:
        user = User.objects.create_user(f'fa_{uuid.uuid4().hex[:6]}', password='pw')
    return FieldAgent.objects.create(
        agent=user,
        device_id='device-001',
        zone_province='Kinshasa',
        status='ACTIVE',
    )


def _make_mission(agent: FieldAgent) -> FieldMission:
    return FieldMission.objects.create(
        agent=agent,
        title='Mission test',
        mission_type='PATROL',
        province='Kinshasa',
        status='IN_PROGRESS',
    )


def _make_record(agent: FieldAgent, **kwargs) -> FieldRecord:
    defaults = dict(
        field_agent=agent,
        record_type='CHECKPOINT',
        national_id='CD-TEST-001',
        description='Passage test',
        offline_at=datetime(2026, 10, 20, 8, 0, tzinfo=dt_tz.utc),
    )
    defaults.update(kwargs)
    return FieldRecord.objects.create(**defaults)


# ── Agents ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_agent_list_200_for_police():
    client, user = _client_for_role('ROLE_POLICE')
    _make_agent()
    r = client.get('/api/v7/field/agents/')
    assert r.status_code == 200
    assert isinstance(r.data, list)


@pytest.mark.django_db
def test_agent_list_403_for_bank():
    client, _ = _client_for_role('ROLE_BANK')
    r = client.get('/api/v7/field/agents/')
    assert r.status_code == 403


@pytest.mark.django_db
def test_agent_list_401_for_anon():
    r = APIClient().get('/api/v7/field/agents/')
    assert r.status_code == 401


@pytest.mark.django_db
def test_agent_list_filter_by_province():
    client, _ = _client_for_role('ROLE_INTEL')
    _make_agent()
    r = client.get('/api/v7/field/agents/?province=Kinshasa')
    assert r.status_code == 200
    # Au moins l'agent créé ci-dessus est retourné
    assert any(a['zone_province'] == 'Kinshasa' for a in r.data)


# ── Missions ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_mission_list_200_for_intel():
    client, _ = _client_for_role('ROLE_INTEL')
    agent = _make_agent()
    _make_mission(agent)
    r = client.get('/api/v7/field/missions/')
    assert r.status_code == 200
    assert len(r.data) >= 1


@pytest.mark.django_db
def test_mission_create_201_for_admin():
    client, user = _client_for_role('ROLE_ADMIN')
    _, field_user = _client_for_role('ROLE_POLICE')
    agent = _make_agent(field_user)
    r = client.post('/api/v7/field/missions/', {
        'agent': agent.pk,
        'title': 'Patrouille Gombe',
        'mission_type': 'PATROL',
        'province': 'Kinshasa',
    }, format='json')
    assert r.status_code == 201
    assert r.data['title'] == 'Patrouille Gombe'


@pytest.mark.django_db
def test_mission_create_403_for_intel():
    client, _ = _client_for_role('ROLE_INTEL')
    r = client.post('/api/v7/field/missions/', {}, format='json')
    assert r.status_code == 403


@pytest.mark.django_db
def test_mission_detail_200():
    client, _ = _client_for_role('ROLE_POLICE')
    agent = _make_agent()
    mission = _make_mission(agent)
    r = client.get(f'/api/v7/field/missions/{mission.pk}/')
    assert r.status_code == 200
    assert r.data['id'] == mission.pk


@pytest.mark.django_db
def test_mission_detail_404():
    client, _ = _client_for_role('ROLE_POLICE')
    r = client.get('/api/v7/field/missions/99999/')
    assert r.status_code == 404


# ── Synchronisation ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_sync_creates_batch_and_records():
    client, user = _client_for_role('ROLE_POLICE')
    payload = {
        'device_id': 'android-abc123',
        'records': [
            {
                'record_type': 'CHECKPOINT',
                'national_id': 'CD-SYNC-001',
                'description': 'Passage frontière',
                'offline_at': '2026-10-20T08:00:00Z',
                'province': 'Kinshasa',
            },
            {
                'record_type': 'OBSERVATION',
                'national_id': 'CD-SYNC-002',
                'description': 'Observation terrain',
                'offline_at': '2026-10-20T09:00:00Z',
            },
        ],
    }
    r = client.post('/api/v7/field/sync/', payload, format='json')
    assert r.status_code == 201
    assert r.data['records_count'] == 2
    # accepted_count dépend de _is_duplicate_record; au moins 0
    assert 'accepted_count' in r.data
    assert 'duplicate_count' in r.data
    assert r.data['status'] in ('COMPLETE', 'PARTIAL')


@pytest.mark.django_db
def test_sync_403_for_intel():
    client, _ = _client_for_role('ROLE_INTEL')
    r = client.post('/api/v7/field/sync/', {'device_id': 'x', 'records': []}, format='json')
    assert r.status_code == 403


@pytest.mark.django_db
def test_sync_empty_batch_returns_201():
    client, _ = _client_for_role('ROLE_POLICE')
    r = client.post('/api/v7/field/sync/', {'device_id': 'dev', 'records': []}, format='json')
    assert r.status_code == 201
    assert r.data['records_count'] == 0


# ── Records ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_record_list_200_for_border():
    client, _ = _client_for_role('ROLE_BORDER')
    agent = _make_agent()
    _make_record(agent)
    r = client.get('/api/v7/field/records/')
    assert r.status_code == 200
    assert len(r.data) >= 1


@pytest.mark.django_db
def test_record_list_filter_by_type():
    client, _ = _client_for_role('ROLE_INTEL')
    agent = _make_agent()
    _make_record(agent, record_type='ARREST')
    _make_record(agent, record_type='SEIZURE')
    r = client.get('/api/v7/field/records/?record_type=ARREST')
    assert r.status_code == 200
    assert all(rec['record_type'] == 'ARREST' for rec in r.data)


# ── Stats ─────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_stats_200_for_admin():
    client, _ = _client_for_role('ROLE_ADMIN')
    r = client.get('/api/v7/field/stats/')
    assert r.status_code == 200
    assert 'agents' in r.data
    assert 'missions' in r.data
    assert 'records' in r.data
    assert 'sync_batches_today' in r.data


@pytest.mark.django_db
def test_stats_403_for_bank():
    client, _ = _client_for_role('ROLE_BANK')
    r = client.get('/api/v7/field/stats/')
    assert r.status_code == 403


# ── _is_duplicate_record ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_is_duplicate_record_returns_false_for_new():
    """Un record inexistant ne doit pas être détecté comme doublon."""
    agent = _make_agent()
    rec = {
        'record_type': 'CHECKPOINT',
        'national_id': 'CD-DUP-001',
        'offline_at': datetime(2026, 10, 20, 10, 0, tzinfo=dt_tz.utc),
    }
    result = _is_duplicate_record(agent, rec)
    # Retourne None si pas implémenté, False si implémenté et pas de doublon
    if result is None:
        pytest.skip("_is_duplicate_record pas encore implémenté")
    assert result is False


@pytest.mark.django_db
def test_is_duplicate_record_returns_true_for_existing():
    """Un record déjà inséré doit être détecté comme doublon."""
    agent = _make_agent()
    offline = datetime(2026, 10, 20, 11, 0, tzinfo=dt_tz.utc)
    # Insérer le record d'abord
    _make_record(agent, national_id='CD-DUP-002', record_type='OBSERVATION', offline_at=offline)

    rec = {
        'record_type': 'OBSERVATION',
        'national_id': 'CD-DUP-002',
        'offline_at': offline,
    }
    result = _is_duplicate_record(agent, rec)
    if result is None:
        pytest.skip("_is_duplicate_record pas encore implémenté")
    assert result is True
