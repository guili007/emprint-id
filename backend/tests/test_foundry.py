"""Tests Module 03 — Eyeshield Foundry Banking."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.biometric.models import AgentProfile
from apps.foundry.models import SectorTenant, TenantAgent, FraudAlert, KYCRecord
from apps.foundry.fraud import _severity_for_count

User = get_user_model()


# ── Helpers fixtures ──────────────────────────────────────────────────────────

def _bank_client_for(user):
    token = AccessToken.for_user(user)
    token['role'] = 'ROLE_BANK'
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
    return c


@pytest.fixture
def rawbank(db):
    return SectorTenant.objects.create(name='Rawbank', sector='BANKING')

@pytest.fixture
def equity_bank(db):
    return SectorTenant.objects.create(name='Equity BCDC', sector='BANKING')

@pytest.fixture
def tmb(db):
    return SectorTenant.objects.create(name='TMB', sector='BANKING')


@pytest.fixture
def bank_agent(db, rawbank):
    u = User.objects.create_user('rawbank_agent', password='pw')
    AgentProfile.objects.create(user=u, role='ROLE_BANK')
    TenantAgent.objects.create(user=u, tenant=rawbank)
    return u

@pytest.fixture
def bank_admin(db, rawbank):
    u = User.objects.create_user('rawbank_admin', password='pw')
    AgentProfile.objects.create(user=u, role='ROLE_BANK')
    TenantAgent.objects.create(user=u, tenant=rawbank, is_admin=True)
    return u

@pytest.fixture
def equity_agent(db, equity_bank):
    u = User.objects.create_user('equity_agent', password='pw')
    AgentProfile.objects.create(user=u, role='ROLE_BANK')
    TenantAgent.objects.create(user=u, tenant=equity_bank)
    return u

@pytest.fixture
def tmb_agent(db, tmb):
    u = User.objects.create_user('tmb_agent', password='pw')
    AgentProfile.objects.create(user=u, role='ROLE_BANK')
    TenantAgent.objects.create(user=u, tenant=tmb)
    return u


# ── Modèles ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_sector_tenant_created(rawbank):
    assert rawbank.sector == 'BANKING'
    assert rawbank.is_active is True

@pytest.mark.django_db
def test_tenant_agent_link(bank_agent, rawbank):
    assert TenantAgent.objects.filter(user=bank_agent, tenant=rawbank).exists()


# ── Sévérité fraude ───────────────────────────────────────────────────────────

def test_severity_low():
    assert _severity_for_count(2) == 'LOW'

def test_severity_medium_3():
    assert _severity_for_count(3) == 'MEDIUM'

def test_severity_medium_4():
    assert _severity_for_count(4) == 'MEDIUM'

def test_severity_high():
    assert _severity_for_count(5) == 'HIGH'

def test_severity_high_many():
    assert _severity_for_count(10) == 'HIGH'


# ── KYC endpoint ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_kyc_non_conforme_citizen_not_found(bank_agent):
    client = _bank_client_for(bank_agent)
    resp = client.post('/api/v3/foundry/banking/kyc/', {'national_id': 'INCONNU-999'})
    assert resp.status_code == 200
    assert resp.data['kyc_status'] == 'NON_CONFORME'

@pytest.mark.django_db
def test_kyc_non_conforme_no_embedding(bank_agent, citizen):
    client = _bank_client_for(bank_agent)
    resp = client.post('/api/v3/foundry/banking/kyc/', {'national_id': citizen.national_id})
    assert resp.status_code == 200
    assert resp.data['kyc_status'] == 'NON_CONFORME'

@pytest.mark.django_db
def test_kyc_conforme_with_embedding(bank_agent, citizen_with_embedding):
    client = _bank_client_for(bank_agent)
    resp = client.post(
        '/api/v3/foundry/banking/kyc/', {'national_id': citizen_with_embedding.national_id}
    )
    assert resp.status_code == 200
    assert resp.data['kyc_status'] == 'CONFORME'

@pytest.mark.django_db
def test_kyc_returns_tenant_name(bank_agent, rawbank, citizen_with_embedding):
    client = _bank_client_for(bank_agent)
    resp = client.post(
        '/api/v3/foundry/banking/kyc/', {'national_id': citizen_with_embedding.national_id}
    )
    assert resp.data['tenant'] == 'Rawbank'

@pytest.mark.django_db
def test_kyc_anon_blocked(anon_client, citizen):
    resp = anon_client.post('/api/v3/foundry/banking/kyc/', {'national_id': citizen.national_id})
    assert resp.status_code == 401

@pytest.mark.django_db
def test_kyc_police_blocked(police_client, citizen):
    resp = police_client.post('/api/v3/foundry/banking/kyc/', {'national_id': citizen.national_id})
    assert resp.status_code == 403

@pytest.mark.django_db
def test_kyc_no_national_id(bank_agent):
    client = _bank_client_for(bank_agent)
    resp = client.post('/api/v3/foundry/banking/kyc/', {})
    assert resp.status_code == 400

@pytest.mark.django_db
def test_kyc_records_attempt(bank_agent, rawbank, citizen_with_embedding):
    client = _bank_client_for(bank_agent)
    client.post('/api/v3/foundry/banking/kyc/', {'national_id': citizen_with_embedding.national_id})
    assert KYCRecord.objects.filter(
        national_id=citizen_with_embedding.national_id, tenant=rawbank
    ).exists()

@pytest.mark.django_db
def test_kyc_no_watchlist_in_response(bank_agent, citizen_with_embedding, watchlist_entry_civil):
    """Silent Flagging : la réponse KYC ne contient aucune info watchlist."""
    client = _bank_client_for(bank_agent)
    resp = client.post(
        '/api/v3/foundry/banking/kyc/', {'national_id': citizen_with_embedding.national_id}
    )
    assert 'watchlist' not in resp.data
    assert 'alert_level' not in resp.data
    assert 'on_watchlist' not in resp.data


# ── Détection fraude inter-bancaire ──────────────────────────────────────────

@pytest.mark.django_db
def test_fraud_alert_created_on_second_bank(
    bank_agent, equity_agent, citizen_with_embedding, rawbank, equity_bank
):
    # Rawbank vérifie
    c1 = _bank_client_for(bank_agent)
    c1.post('/api/v3/foundry/banking/kyc/', {'national_id': citizen_with_embedding.national_id})
    # Equity vérifie le même ID
    c2 = _bank_client_for(equity_agent)
    c2.post('/api/v3/foundry/banking/kyc/', {'national_id': citizen_with_embedding.national_id})

    alert = FraudAlert.objects.filter(national_id=citizen_with_embedding.national_id).first()
    assert alert is not None
    assert alert.severity == 'LOW'
    assert alert.tenant_count == 2

@pytest.mark.django_db
def test_no_fraud_alert_single_bank(bank_agent, citizen_with_embedding):
    c = _bank_client_for(bank_agent)
    c.post('/api/v3/foundry/banking/kyc/', {'national_id': citizen_with_embedding.national_id})
    assert not FraudAlert.objects.filter(
        national_id=citizen_with_embedding.national_id
    ).exists()


# ── Fraud Alert List ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_fraud_alert_list_bank_admin(bank_admin, rawbank, citizen_with_embedding):
    FraudAlert.objects.create(
        national_id=citizen_with_embedding.national_id,
        severity='LOW', tenant_count=2,
        tenant_names=['Rawbank', 'Equity BCDC'],
    )
    client = _bank_client_for(bank_admin)
    resp = client.get('/api/v3/foundry/banking/fraud-alerts/')
    assert resp.status_code == 200
    assert resp.data['count'] == 1

@pytest.mark.django_db
def test_fraud_alert_list_non_admin_blocked(bank_agent):
    client = _bank_client_for(bank_agent)
    resp = client.get('/api/v3/foundry/banking/fraud-alerts/')
    assert resp.status_code == 403

@pytest.mark.django_db
def test_fraud_alert_list_admin_role(admin_client):
    FraudAlert.objects.create(
        national_id='TEST-001', severity='HIGH',
        tenant_count=5, tenant_names=['A', 'B', 'C', 'D', 'E'],
    )
    resp = admin_client.get('/api/v3/foundry/banking/fraud-alerts/')
    assert resp.status_code == 200
    assert resp.data['count'] >= 1
