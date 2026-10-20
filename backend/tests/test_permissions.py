"""Tests permissions RBAC — IsFieldAgent et IsWatchlistAdmin."""
import pytest


# ── IsFieldAgent ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_police_can_access_verify(police_client, citizen):
    resp = police_client.post('/api/v2/verify/', {'image': 'data:image/jpeg;base64,/9j/'}, format='json')
    # 400 (validation) ou 422 (pas de vrai modèle) — jamais 401/403
    assert resp.status_code not in (401, 403)

@pytest.mark.django_db
def test_bank_can_access_verify(bank_client, citizen):
    resp = bank_client.post('/api/v2/verify/', {'image': 'data:image/jpeg;base64,/9j/'}, format='json')
    assert resp.status_code not in (401, 403)

@pytest.mark.django_db
def test_border_can_access_verify(border_client, citizen):
    resp = border_client.post('/api/v2/verify/', {'image': 'data:image/jpeg;base64,/9j/'}, format='json')
    assert resp.status_code not in (401, 403)

@pytest.mark.django_db
def test_admin_can_access_verify(admin_client, citizen):
    """Les admins sont aussi dans FIELD_ROLES | ADMIN_ROLES."""
    resp = admin_client.post('/api/v2/verify/', {'image': 'data:image/jpeg;base64,/9j/'}, format='json')
    assert resp.status_code not in (401, 403)

@pytest.mark.django_db
def test_anon_blocked_from_verify(anon_client, citizen):
    resp = anon_client.post('/api/v2/verify/', {'image': 'data:image/jpeg;base64,/9j/'}, format='json')
    assert resp.status_code == 401


# ── IsWatchlistAdmin ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_watchlist_admin_can_post_watchlist(watchlist_admin_client, citizen):
    resp = watchlist_admin_client.post('/api/v2/watchlist/', {
        'citizen': citizen.pk,
        'alert_level': 'JAUNE',
        'authority': 'CIVIL',
        'reason': 'Test permission',
        'issued_by': 'Test',
    }, format='json')
    assert resp.status_code == 201

@pytest.mark.django_db
def test_police_blocked_from_posting_watchlist(police_client, citizen):
    resp = police_client.post('/api/v2/watchlist/', {
        'citizen': citizen.pk,
        'alert_level': 'JAUNE',
        'authority': 'CIVIL',
        'reason': 'Tentative',
        'issued_by': 'Test',
    }, format='json')
    assert resp.status_code == 403

@pytest.mark.django_db
def test_bank_blocked_from_posting_watchlist(bank_client, citizen):
    resp = bank_client.post('/api/v2/watchlist/', {
        'citizen': citizen.pk,
        'alert_level': 'ORANGE',
        'authority': 'CIVIL',
        'reason': 'Tentative',
        'issued_by': 'Test',
    }, format='json')
    assert resp.status_code == 403

@pytest.mark.django_db
def test_plain_admin_blocked_from_watchlist(admin_client, citizen):
    """ROLE_ADMIN seul est BLOQUÉ — seul ROLE_WATCHLIST_ADMIN est autorisé."""
    resp = admin_client.post('/api/v2/watchlist/', {
        'citizen': citizen.pk,
        'alert_level': 'ROUGE',
        'authority': 'CIVIL',
        'reason': 'Tentative admin',
        'issued_by': 'Test',
    }, format='json')
    assert resp.status_code == 403

@pytest.mark.django_db
def test_anon_blocked_from_watchlist(anon_client, citizen):
    resp = anon_client.post('/api/v2/watchlist/', {'citizen': citizen.pk}, format='json')
    assert resp.status_code == 401
