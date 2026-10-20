"""Tests JWT RBAC — rôle injecté dans le token, lu dans les réponses."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_token_contains_role(bank_user):
    """Le JWT doit contenir le champ 'role' avec la valeur du profil."""
    import base64, json
    client = APIClient()
    resp = client.post('/api/token/', {'username': 'test_bank', 'password': 'pw'}, format='json')
    assert resp.status_code == 200
    access = resp.data['access']
    payload = json.loads(base64.b64decode(access.split('.')[1] + '=='))
    assert payload['role'] == 'ROLE_BANK'

@pytest.mark.django_db
def test_token_contains_username(police_user):
    import base64, json
    client = APIClient()
    resp = client.post('/api/token/', {'username': 'test_police', 'password': 'pw'}, format='json')
    payload = json.loads(base64.b64decode(resp.data['access'].split('.')[1] + '=='))
    assert payload['username'] == 'test_police'

@pytest.mark.django_db
def test_anon_blocked_on_biometric_endpoint(anon_client):
    resp = anon_client.post('/api/v2/verify/', {'image': 'data'}, format='json')
    assert resp.status_code == 401

@pytest.mark.django_db
def test_wrong_credentials_rejected():
    client = APIClient()
    resp = client.post('/api/token/', {'username': 'nobody', 'password': 'wrong'}, format='json')
    assert resp.status_code == 401
