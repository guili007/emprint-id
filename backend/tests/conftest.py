"""Fixtures partagées pour tous les tests EmPrint-iD."""
import math
import random
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.citizens.models import Citizen, Province, Commune
from apps.biometric.models import AgentProfile, CitizenFaceEmbedding, WatchlistEntry

User = get_user_model()


def _make_embedding():
    v = [random.gauss(0, 1) for _ in range(512)]
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


# ── Utilisateurs par rôle ─────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    u = User.objects.create_user('test_admin', password='pw', is_superuser=True)
    AgentProfile.objects.create(user=u, role='ROLE_ADMIN')
    return u

@pytest.fixture
def bank_user(db):
    u = User.objects.create_user('test_bank', password='pw')
    AgentProfile.objects.create(user=u, role='ROLE_BANK')
    return u

@pytest.fixture
def police_user(db):
    u = User.objects.create_user('test_police', password='pw')
    AgentProfile.objects.create(user=u, role='ROLE_POLICE')
    return u

@pytest.fixture
def border_user(db):
    u = User.objects.create_user('test_border', password='pw')
    AgentProfile.objects.create(user=u, role='ROLE_BORDER')
    return u

@pytest.fixture
def watchlist_admin_user(db):
    u = User.objects.create_user('test_wl_admin', password='pw')
    AgentProfile.objects.create(user=u, role='ROLE_WATCHLIST_ADMIN')
    return u


# ── Client API avec JWT ───────────────────────────────────────────────────────

def _api_client_for(user):
    """Retourne un APIClient avec le JWT du user (rôle injecté)."""
    token = AccessToken.for_user(user)
    try:
        token['role'] = user.profile.role
    except Exception:
        token['role'] = ''
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
    return client

@pytest.fixture
def admin_client(admin_user):
    return _api_client_for(admin_user)

@pytest.fixture
def bank_client(bank_user):
    return _api_client_for(bank_user)

@pytest.fixture
def police_client(police_user):
    return _api_client_for(police_user)

@pytest.fixture
def border_client(border_user):
    return _api_client_for(border_user)

@pytest.fixture
def watchlist_admin_client(watchlist_admin_user):
    return _api_client_for(watchlist_admin_user)

@pytest.fixture
def anon_client():
    return APIClient()


# ── Géographie + Citoyen ─────────────────────────────────────────────────────

@pytest.fixture
def province(db):
    return Province.objects.create(code='KN', nom='Kinshasa')

@pytest.fixture
def commune(db, province):
    return Commune.objects.create(code='GBE', nom='Gombe', province=province)

@pytest.fixture
def citizen(db, province, commune):
    return Citizen.objects.create(
        national_id='CG-KN-GBE-999001-T1',
        nom='Mutombo', postnom='Test', prenom='Jean',
        sexe='M', province=province, commune=commune,
    )

@pytest.fixture
def citizen_with_embedding(db, citizen):
    CitizenFaceEmbedding.objects.create(
        citizen=citizen,
        embedding=_make_embedding(),
        liveness_score=0.92,
        quality_score=0.88,
    )
    return citizen


# ── Watchlist ─────────────────────────────────────────────────────────────────

@pytest.fixture
def watchlist_entry_civil(db, citizen, admin_user):
    return WatchlistEntry.objects.create(
        citizen=citizen,
        alert_level='ROUGE',
        authority='CIVIL',
        reason='Test CIVIL',
        issued_by='PNC',
        created_by=admin_user,
    )

@pytest.fixture
def watchlist_entry_military(db, citizen, admin_user):
    return WatchlistEntry.objects.create(
        citizen=citizen,
        alert_level='ROUGE',
        authority='MILITAIRE',
        reason='Test MILITAIRE',
        issued_by='FARDC',
        created_by=admin_user,
    )
