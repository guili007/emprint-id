"""Tests watchlist — authority choices, check endpoint, deactivation."""
import pytest
from apps.biometric.models import WatchlistEntry


# ── Authority choices ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_watchlist_entry_civil_authority(watchlist_entry_civil):
    assert watchlist_entry_civil.authority == 'CIVIL'

@pytest.mark.django_db
def test_watchlist_entry_military_authority(watchlist_entry_military):
    assert watchlist_entry_military.authority == 'MILITAIRE'

@pytest.mark.django_db
def test_create_etat_authority(watchlist_admin_client, citizen):
    resp = watchlist_admin_client.post('/api/v2/watchlist/', {
        'citizen': citizen.pk,
        'alert_level': 'ROUGE',
        'authority': 'ETAT',
        'reason': 'Diffusion générale',
        'issued_by': 'Cabinet du Premier Ministre',
    }, format='json')
    assert resp.status_code == 201
    assert resp.data['authority'] == 'ETAT'

@pytest.mark.django_db
def test_invalid_authority_rejected(watchlist_admin_client, citizen):
    resp = watchlist_admin_client.post('/api/v2/watchlist/', {
        'citizen': citizen.pk,
        'alert_level': 'ROUGE',
        'authority': 'FANTOME',
        'reason': 'Test invalide',
        'issued_by': 'Test',
    }, format='json')
    assert resp.status_code == 400


# ── WatchlistCheck endpoint ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_check_returns_on_watchlist_true(police_client, citizen, watchlist_entry_civil):
    resp = police_client.get(f'/api/v2/watchlist/check/{citizen.pk}/')
    assert resp.status_code == 200
    assert resp.data['on_watchlist'] is True
    assert resp.data['alert_level'] == 'ROUGE'

@pytest.mark.django_db
def test_check_returns_on_watchlist_false(police_client, citizen):
    resp = police_client.get(f'/api/v2/watchlist/check/{citizen.pk}/')
    assert resp.status_code == 200
    assert resp.data['on_watchlist'] is False

@pytest.mark.django_db
def test_check_response_is_signed(police_client, citizen, watchlist_entry_civil):
    """La réponse doit contenir un HMAC (signature)."""
    resp = police_client.get(f'/api/v2/watchlist/check/{citizen.pk}/')
    assert 'hmac' in resp.data

@pytest.mark.django_db
def test_check_404_for_unknown_citizen(police_client):
    import uuid
    fake_uuid = uuid.UUID('00000000-0000-0000-0000-000000000000')
    resp = police_client.get(f'/api/v2/watchlist/check/{fake_uuid}/')
    assert resp.status_code == 404

@pytest.mark.django_db
def test_check_inactive_entry_not_returned(police_client, citizen, watchlist_entry_civil):
    watchlist_entry_civil.is_active = False
    watchlist_entry_civil.save()
    resp = police_client.get(f'/api/v2/watchlist/check/{citizen.pk}/')
    assert resp.data['on_watchlist'] is False


# ── Rouge prioritaire sur Orange ─────────────────────────────────────────────

@pytest.mark.django_db
def test_check_returns_highest_alert_level(police_client, citizen, admin_user):
    from apps.biometric.models import WatchlistEntry
    WatchlistEntry.objects.create(
        citizen=citizen, alert_level='JAUNE', authority='CIVIL',
        reason='Bas', issued_by='PNC', created_by=admin_user,
    )
    WatchlistEntry.objects.create(
        citizen=citizen, alert_level='ROUGE', authority='CIVIL',
        reason='Haut', issued_by='PNC', created_by=admin_user,
    )
    resp = police_client.get(f'/api/v2/watchlist/check/{citizen.pk}/')
    assert resp.data['alert_level'] == 'ROUGE'


# ── Désactivation ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_deactivate_watchlist_entry(watchlist_admin_client, watchlist_entry_civil):
    resp = watchlist_admin_client.delete(f'/api/v2/watchlist/{watchlist_entry_civil.pk}/')
    assert resp.status_code == 204
    watchlist_entry_civil.refresh_from_db()
    assert watchlist_entry_civil.is_active is False

@pytest.mark.django_db
def test_deactivate_does_not_delete(watchlist_admin_client, watchlist_entry_civil):
    pk = watchlist_entry_civil.pk
    watchlist_admin_client.delete(f'/api/v2/watchlist/{pk}/')
    assert WatchlistEntry.objects.filter(pk=pk).exists()
