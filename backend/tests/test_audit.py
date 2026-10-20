"""
Tests Module 05 — Eyeshield Audit.

Couvre :
  - AuditEventListView         : liste, filtres event_type/date/role
  - AuditStatsView             : agrégation cross-app
  - ComplianceFlagListView     : liste, filtres status/type/severity
  - ComplianceFlagStatusView   : PATCH REVIEWED / DISMISSED, règles métier
  - AuditReportListCreateView  : liste + POST génération rapport
  - AuditReportDetailView      : détail + summary calculé
  - RBAC                       : ROLE_ADMIN OK, ROLE_POLICE 403, anonyme 401
"""
import uuid
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditEvent, AuditReport, ComplianceFlag

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_for_role(role: str) -> APIClient:
    user = User.objects.create_user(f'audit_{uuid.uuid4().hex[:6]}', password='pw')
    token = AccessToken.for_user(user)
    token['role'] = role
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
    return client, user


def _make_event(**kwargs) -> AuditEvent:
    defaults = dict(
        event_type=AuditEvent.EventType.DATA_ACCESS,
        actor_role='ROLE_POLICE',
        target_national_id='CD-AUDIT-001',
    )
    defaults.update(kwargs)
    return AuditEvent.objects.create(**defaults)


def _make_flag(**kwargs) -> ComplianceFlag:
    defaults = dict(
        flag_type=ComplianceFlag.FlagType.HIGH_FREQUENCY,
        severity=ComplianceFlag.Severity.MEDIUM,
        actor_role='ROLE_BANK',
        description='Test flag',
    )
    defaults.update(kwargs)
    return ComplianceFlag.objects.create(**defaults)


# ── AuditEventListView ────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_audit_event_list_200_for_admin():
    client, _ = _client_for_role('ROLE_ADMIN')
    _make_event()
    r = client.get('/api/v5/audit/events/')
    assert r.status_code == 200
    assert len(r.data) >= 1


@pytest.mark.django_db
def test_audit_event_list_403_for_police():
    client, _ = _client_for_role('ROLE_POLICE')
    r = client.get('/api/v5/audit/events/')
    assert r.status_code == 403


@pytest.mark.django_db
def test_audit_event_list_401_for_anon():
    r = APIClient().get('/api/v5/audit/events/')
    assert r.status_code == 401


@pytest.mark.django_db
def test_audit_event_list_filter_by_type():
    client, _ = _client_for_role('ROLE_ADMIN')
    _make_event(event_type='LOGIN')
    _make_event(event_type='DATA_ACCESS')
    r = client.get('/api/v5/audit/events/?event_type=LOGIN')
    assert r.status_code == 200
    assert all(e['event_type'] == 'LOGIN' for e in r.data)


# ── AuditStatsView ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_audit_stats_200_for_admin():
    client, _ = _client_for_role('ROLE_ADMIN')
    r = client.get('/api/v5/audit/stats/')
    assert r.status_code == 200
    # Structure attendue
    assert 'verifications' in r.data
    assert 'intel_alerts' in r.data
    assert 'compliance_flags' in r.data
    assert 'audit_events_today' in r.data


@pytest.mark.django_db
def test_audit_stats_403_for_bank():
    client, _ = _client_for_role('ROLE_BANK')
    r = client.get('/api/v5/audit/stats/')
    assert r.status_code == 403


# ── ComplianceFlagListView ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_compliance_flag_list_200():
    client, _ = _client_for_role('ROLE_WATCHLIST_ADMIN')
    _make_flag()
    r = client.get('/api/v5/audit/flags/')
    assert r.status_code == 200
    assert len(r.data) >= 1


@pytest.mark.django_db
def test_compliance_flag_list_filter_by_status():
    client, _ = _client_for_role('ROLE_ADMIN')
    _make_flag(status='OPEN')
    _make_flag(status='DISMISSED')
    r = client.get('/api/v5/audit/flags/?status=OPEN')
    assert r.status_code == 200
    assert all(f['status'] == 'OPEN' for f in r.data)


# ── ComplianceFlagStatusView ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_compliance_flag_status_patch_to_reviewed():
    client, _ = _client_for_role('ROLE_ADMIN')
    flag = _make_flag()
    r = client.patch(f'/api/v5/audit/flags/{flag.pk}/status/', {'status': 'REVIEWED'})
    assert r.status_code == 200
    assert r.data['status'] == 'REVIEWED'
    assert r.data['reviewed_at'] is not None


@pytest.mark.django_db
def test_compliance_flag_status_patch_to_dismissed():
    client, _ = _client_for_role('ROLE_WATCHLIST_ADMIN')
    flag = _make_flag()
    r = client.patch(f'/api/v5/audit/flags/{flag.pk}/status/', {'status': 'DISMISSED'})
    assert r.status_code == 200
    assert r.data['status'] == 'DISMISSED'


@pytest.mark.django_db
def test_compliance_flag_already_reviewed_returns_409():
    """
    TODO(human): Implémente ce test.

    Contexte : Un flag déjà REVIEWED ne doit pas pouvoir être re-patché.
    La vue retourne 409 CONFLICT dans ce cas.

    Étapes :
    1. Créer un flag en OPEN
    2. Le patcher vers REVIEWED (premier PATCH, doit réussir)
    3. Tenter un second PATCH vers DISMISSED sur le même flag
    4. Vérifier que le second PATCH retourne 409
    """
    pass  # TODO(human)


# ── AuditReportListCreateView ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_audit_report_list_200():
    client, user = _client_for_role('ROLE_ADMIN')
    AuditReport.objects.create(
        report_type='DAILY',
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 1),
        generated_by=user,
        status='COMPLETE',
        summary={'total_verifications': 42},
    )
    r = client.get('/api/v5/audit/reports/')
    assert r.status_code == 200
    assert len(r.data) >= 1


@pytest.mark.django_db
def test_audit_report_create_generates_summary():
    client, _ = _client_for_role('ROLE_ADMIN')
    payload = {
        'report_type': 'CUSTOM',
        'period_start': '2026-10-01',
        'period_end':   '2026-10-20',
    }
    r = client.post('/api/v5/audit/reports/', payload)
    assert r.status_code == 201
    assert r.data['status'] == 'COMPLETE'
    # Le summary doit contenir les clés attendues
    assert 'total_verifications' in r.data['summary']
    assert 'compliance_flags_open' in r.data['summary']


@pytest.mark.django_db
def test_audit_report_detail_200():
    client, user = _client_for_role('ROLE_ADMIN')
    report = AuditReport.objects.create(
        report_type='WEEKLY',
        period_start=date(2026, 10, 14),
        period_end=date(2026, 10, 20),
        generated_by=user,
        status='COMPLETE',
        summary={'total_verifications': 10},
    )
    r = client.get(f'/api/v5/audit/reports/{report.pk}/')
    assert r.status_code == 200
    assert r.data['id'] == report.pk
    assert r.data['summary']['total_verifications'] == 10


@pytest.mark.django_db
def test_audit_report_detail_404():
    client, _ = _client_for_role('ROLE_ADMIN')
    r = client.get('/api/v5/audit/reports/99999/')
    assert r.status_code == 404
