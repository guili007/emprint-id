"""Tests Module 02 — Eyeshield Data (recherche unifiée + analytics + logs)."""
import pytest
from apps.biometric.models import VerificationLog


# ── Recherche unifiée /api/v2/data/citizens/search/ ───────────────────────────

@pytest.mark.django_db
def test_search_returns_citizens(police_client, citizen):
    resp = police_client.get('/api/v2/data/citizens/search/')
    assert resp.status_code == 200
    assert resp.data['count'] >= 1

@pytest.mark.django_db
def test_search_filter_by_national_id(police_client, citizen):
    resp = police_client.get(f'/api/v2/data/citizens/search/?q={citizen.national_id}')
    assert resp.status_code == 200
    assert resp.data['count'] == 1
    assert resp.data['results'][0]['national_id'] == citizen.national_id

@pytest.mark.django_db
def test_search_filter_by_province(police_client, citizen, province):
    resp = police_client.get(f'/api/v2/data/citizens/search/?province={province.code}')
    assert resp.status_code == 200
    assert resp.data['count'] >= 1

@pytest.mark.django_db
def test_search_anon_blocked(anon_client):
    resp = anon_client.get('/api/v2/data/citizens/search/')
    assert resp.status_code == 401

@pytest.mark.django_db
def test_search_has_embedding_flag(police_client, citizen_with_embedding):
    resp = police_client.get(f'/api/v2/data/citizens/search/?q={citizen_with_embedding.national_id}')
    result = resp.data['results'][0]
    assert result['has_embedding'] is True

@pytest.mark.django_db
def test_search_no_embedding_flag(police_client, citizen):
    resp = police_client.get(f'/api/v2/data/citizens/search/?q={citizen.national_id}')
    result = resp.data['results'][0]
    assert result['has_embedding'] is False


# ── Silent Flagging dans la recherche ─────────────────────────────────────────

@pytest.mark.django_db
def test_bank_sees_no_watchlist_in_search(bank_client, citizen, watchlist_entry_civil):
    resp = bank_client.get(f'/api/v2/data/citizens/search/?q={citizen.national_id}')
    result = resp.data['results'][0]
    assert result['watchlist'] is None, "VIOLATION Silent Flagging: BANK voit la watchlist"

@pytest.mark.django_db
def test_police_sees_civil_watchlist(police_client, citizen, watchlist_entry_civil):
    resp = police_client.get(f'/api/v2/data/citizens/search/?q={citizen.national_id}')
    result = resp.data['results'][0]
    assert result['watchlist'] is not None
    assert len(result['watchlist']) == 1
    assert result['watchlist'][0]['authority'] == 'CIVIL'

@pytest.mark.django_db
def test_police_does_not_see_military_watchlist(police_client, citizen, watchlist_entry_military):
    resp = police_client.get(f'/api/v2/data/citizens/search/?q={citizen.national_id}')
    result = resp.data['results'][0]
    # POLICE ne voit pas MILITAIRE
    assert result['watchlist'] == []

@pytest.mark.django_db
def test_border_sees_military_watchlist(border_client, citizen, watchlist_entry_military):
    resp = border_client.get(f'/api/v2/data/citizens/search/?q={citizen.national_id}')
    result = resp.data['results'][0]
    assert result['watchlist'] is not None
    assert len(result['watchlist']) == 1
    assert result['watchlist'][0]['authority'] == 'MILITAIRE'

@pytest.mark.django_db
def test_admin_sees_all_watchlist(admin_client, citizen, watchlist_entry_civil, watchlist_entry_military):
    resp = admin_client.get(f'/api/v2/data/citizens/search/?q={citizen.national_id}')
    result = resp.data['results'][0]
    assert len(result['watchlist']) == 2


# ── Logs /api/v2/data/logs/ ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_admin_sees_all_logs(admin_client, citizen, admin_user, police_user):
    VerificationLog.objects.create(
        citizen=citizen, agent_user=admin_user,
        status='VERIFIED', agent_role='ROLE_ADMIN',
    )
    VerificationLog.objects.create(
        citizen=citizen, agent_user=police_user,
        status='REJECTED_FACE', agent_role='ROLE_POLICE',
    )
    resp = admin_client.get('/api/v2/data/logs/')
    assert resp.status_code == 200
    assert resp.data['count'] == 2

@pytest.mark.django_db
def test_police_sees_only_own_logs(police_client, citizen, police_user, admin_user):
    VerificationLog.objects.create(
        citizen=citizen, agent_user=police_user,
        status='VERIFIED', agent_role='ROLE_POLICE',
    )
    VerificationLog.objects.create(
        citizen=citizen, agent_user=admin_user,
        status='VERIFIED', agent_role='ROLE_ADMIN',
    )
    resp = police_client.get('/api/v2/data/logs/')
    assert resp.status_code == 200
    assert resp.data['count'] == 1
    assert resp.data['results'][0]['agent_username'] == 'test_police'

@pytest.mark.django_db
def test_logs_filter_by_status(admin_client, citizen, admin_user):
    VerificationLog.objects.create(
        citizen=citizen, agent_user=admin_user,
        status='VERIFIED', agent_role='ROLE_ADMIN',
    )
    VerificationLog.objects.create(
        citizen=citizen, agent_user=admin_user,
        status='REJECTED_FACE', agent_role='ROLE_ADMIN',
    )
    resp = admin_client.get('/api/v2/data/logs/?status=VERIFIED')
    assert resp.data['count'] == 1
    assert resp.data['results'][0]['status'] == 'VERIFIED'

@pytest.mark.django_db
def test_anon_blocked_from_logs(anon_client):
    resp = anon_client.get('/api/v2/data/logs/')
    assert resp.status_code == 401


# ── Stats /api/v2/data/stats/ ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_admin_can_access_stats(admin_client):
    resp = admin_client.get('/api/v2/data/stats/')
    assert resp.status_code == 200
    assert 'total_verifications' in resp.data
    assert 'active_citizens' in resp.data
    assert 'daily_trend' in resp.data

@pytest.mark.django_db
def test_stats_response_is_signed(admin_client):
    resp = admin_client.get('/api/v2/data/stats/')
    assert 'hmac' in resp.data

@pytest.mark.django_db
def test_police_blocked_from_stats(police_client):
    """Les stats globales sont réservées à l'État (ADMIN seulement)."""
    resp = police_client.get('/api/v2/data/stats/')
    assert resp.status_code == 403

@pytest.mark.django_db
def test_bank_blocked_from_stats(bank_client):
    resp = bank_client.get('/api/v2/data/stats/')
    assert resp.status_code == 403

@pytest.mark.django_db
def test_stats_counts_verifications(admin_client, citizen, admin_user):
    VerificationLog.objects.create(
        citizen=citizen, agent_user=admin_user,
        status='VERIFIED', agent_role='ROLE_ADMIN',
    )
    resp = admin_client.get('/api/v2/data/stats/')
    assert resp.data['total_verifications'] >= 1
    assert resp.data['verified'] >= 1
