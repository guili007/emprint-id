"""
Tests Module 02 Eyeshield Data — couche ontologie.

Couvre :
  - DataSourceListView   : liste + filtres secteur, RBAC rôle→secteur
  - CitizenProfileView   : profil unifié, filtrage par rôle
  - DataLinkListCreateView (POST) : upsert lien national_id ↔ source
  - CitizenLinksView     : liste paginée des liens d'un citoyen
  - OntologyStatsView    : stats admin
  - RBAC                 : ROLE_ADMIN, ROLE_BANK, ROLE_HEALTH, anonyme
"""
import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.data.models import CitizenDataLink, DataAccessPolicy, DataSource

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_for_role(role: str) -> APIClient:
    """Crée un APIClient authentifié avec le rôle JWT donné."""
    user = User.objects.create_user(f'onto_{uuid.uuid4().hex[:6]}', password='pw')
    token = AccessToken.for_user(user)
    token['role'] = role
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
    return client


def _make_source(**kwargs) -> DataSource:
    """Crée une DataSource en base."""
    defaults = dict(
        code=f"SRC_{uuid.uuid4().hex[:4].upper()}",
        name="Source de test",
        sector=DataSource.Sector.BANKING,
        is_active=True,
    )
    defaults.update(kwargs)
    return DataSource.objects.create(**defaults)


def _make_link(national_id: str, source: DataSource, **kwargs) -> CitizenDataLink:
    """Crée un CitizenDataLink en base."""
    defaults = dict(external_id=f"EXT-{uuid.uuid4().hex[:6]}")
    defaults.update(kwargs)
    return CitizenDataLink.objects.create(
        national_id=national_id, source=source, **defaults
    )


# ── DataSourceListView ────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_sources_list_200_for_admin():
    """ROLE_ADMIN voit toutes les sources actives."""
    _make_source(code='DGI', name='Direction Générale des Impôts', sector='FISCAL')
    _make_source(code='RAWBANK', name='Rawbank', sector='BANKING')
    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/data/sources/')
    assert response.status_code == 200
    codes = [s['code'] for s in response.data]
    assert 'DGI' in codes
    assert 'RAWBANK' in codes


@pytest.mark.django_db
def test_sources_list_bank_role_only_sees_banking():
    """ROLE_BANK ne voit que les sources BANKING + IDENTITY."""
    _make_source(code='DGI2', sector='FISCAL')
    _make_source(code='RBK2', sector='BANKING')
    client = _client_for_role('ROLE_BANK')
    response = client.get('/api/v3/data/sources/')
    assert response.status_code == 200
    sectors = {s['sector'] for s in response.data}
    assert 'FISCAL' not in sectors
    assert 'BANKING' in sectors or 'IDENTITY' in sectors or len(sectors) == 0


@pytest.mark.django_db
def test_sources_list_401_anon():
    """Anonyme → 401."""
    response = APIClient().get('/api/v3/data/sources/')
    assert response.status_code == 401


@pytest.mark.django_db
def test_sources_list_filter_by_sector():
    """?sector= filtre par secteur."""
    _make_source(code='ARDHI', sector='LAND')
    _make_source(code='MOB', sector='TELECOM')
    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/data/sources/', {'sector': 'LAND'})
    assert response.status_code == 200
    assert all(s['sector'] == 'LAND' for s in response.data)


# ── CitizenProfileView ────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_citizen_profile_200_includes_links():
    """Le profil d'un citoyen inclut ses liens avec les bons champs."""
    nid    = 'CD-TEST-001'
    source = _make_source(code='ONEC', sector='CIVIL')
    _make_link(nid, source, external_id='ACTE-1988-001', label='Acte de naissance')

    client = _client_for_role('ROLE_ADMIN')
    response = client.get(f'/api/v3/data/citizens/{nid}/profile/')
    assert response.status_code == 200
    assert response.data['national_id'] == nid
    assert response.data['total_links'] == 1
    assert response.data['links'][0]['external_id'] == 'ACTE-1988-001'
    assert 'CIVIL' in response.data['linked_sectors']


@pytest.mark.django_db
def test_citizen_profile_empty_for_unknown_id():
    """Un national_id sans liens retourne total_links=0 (pas de 404)."""
    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/data/citizens/CD-INCONNU-999/profile/')
    assert response.status_code == 200
    assert response.data['total_links'] == 0
    assert response.data['links'] == []


@pytest.mark.django_db
def test_citizen_profile_bank_role_filtered():
    """ROLE_BANK ne voit pas les sources LAND d'un citoyen."""
    nid      = 'CD-TEST-002'
    banking  = _make_source(code='RBK3', sector='BANKING')
    land     = _make_source(code='ARDHI2', sector='LAND')
    _make_link(nid, banking, external_id='COMPTE-001')
    _make_link(nid, land,    external_id='PARCELLE-001')

    client = _client_for_role('ROLE_BANK')
    response = client.get(f'/api/v3/data/citizens/{nid}/profile/')
    assert response.status_code == 200
    sectors = {lnk['source_sector'] for lnk in response.data['links']}
    assert 'LAND' not in sectors
    assert 'BANKING' in sectors


# ── DataLinkListCreateView ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_post_link_creates_record():
    """POST /api/v3/data/links/ crée un lien (ADMIN)."""
    source = _make_source(code='SIGA', sector='PUBLIC_SVC')
    client = _client_for_role('ROLE_ADMIN')
    payload = {
        'national_id': 'CD-TEST-003',
        'source':      source.id,
        'external_id': 'FP-2019-4471',
        'label':       'Agent fonction publique',
    }
    response = client.post('/api/v3/data/links/', payload, format='json')
    assert response.status_code == 201
    assert response.data['national_id'] == 'CD-TEST-003'
    assert response.data['external_id'] == 'FP-2019-4471'
    assert CitizenDataLink.objects.filter(national_id='CD-TEST-003').exists()


@pytest.mark.django_db
def test_post_link_upsert_updates_existing():
    """POST avec le même (national_id, source) met à jour le lien existant."""
    source = _make_source(code='SIGA2', sector='PUBLIC_SVC')
    _make_link('CD-TEST-004', source, external_id='OLD-ID')

    client = _client_for_role('ROLE_ADMIN')
    payload = {
        'national_id': 'CD-TEST-004',
        'source':      source.id,
        'external_id': 'NEW-ID',
    }
    response = client.post('/api/v3/data/links/', payload, format='json')
    assert response.status_code == 201
    assert CitizenDataLink.objects.filter(
        national_id='CD-TEST-004', external_id='NEW-ID'
    ).exists()
    # Pas de doublon
    assert CitizenDataLink.objects.filter(national_id='CD-TEST-004').count() == 1


@pytest.mark.django_db
def test_post_link_403_for_bank_role():
    """ROLE_BANK ne peut pas créer de liens (réservé aux admins)."""
    source = _make_source(code='SIGA3', sector='PUBLIC_SVC')
    client = _client_for_role('ROLE_BANK')
    payload = {'national_id': 'CD-TEST-005', 'source': source.id, 'external_id': 'X'}
    response = client.post('/api/v3/data/links/', payload, format='json')
    assert response.status_code == 403


# ── CitizenLinksView ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_citizen_links_paginated():
    """GET /api/v3/data/links/<national_id>/ retourne les liens paginés."""
    nid    = 'CD-TEST-006'
    src1   = _make_source(code='AIRTEL', sector='TELECOM')
    src2   = _make_source(code='ORANGE', sector='TELECOM')
    _make_link(nid, src1, external_id='099001')
    _make_link(nid, src2, external_id='081001')

    client = _client_for_role('ROLE_ADMIN')
    response = client.get(f'/api/v3/data/links/{nid}/')
    assert response.status_code == 200
    assert response.data['count'] == 2


# ── OntologyStatsView ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_ontology_stats_200_for_admin():
    """ROLE_ADMIN peut accéder aux stats ontologie."""
    source = _make_source(code='ONEC2', sector='CIVIL')
    _make_link('CD-STATS-001', source)
    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/data/ontology/stats/')
    assert response.status_code == 200
    assert 'total_sources' in response.data
    assert 'total_links' in response.data
    assert 'citizens_linked' in response.data
    assert response.data['total_links'] >= 1


@pytest.mark.django_db
def test_ontology_stats_403_for_bank():
    """ROLE_BANK n'a pas accès aux stats ontologie."""
    response = _client_for_role('ROLE_BANK').get('/api/v3/data/ontology/stats/')
    assert response.status_code == 403


@pytest.mark.django_db
def test_ontology_stats_coverage_by_sector():
    # TODO(human) — implémenter ce test
    pass
