"""
Tests Module 04 — Eyeshield Intel.

Couvre :
  - IntelAlertListCreateView  : liste + filtres, POST créer alerte
  - IntelAlertDetailView      : détail avec preuves
  - IntelAlertStatusView      : PATCH statut + resolved_at automatique
  - NetworkGraphView          : graphe réseau d'un citoyen
  - NetworkLinkCreateView     : POST lien réseau (upsert)
  - ThreatZoneListCreateView  : liste + filtres, POST créer zone
  - IntelStatsView            : dashboard agrégé (ROLE_INTEL / ADMIN)
  - RBAC                      : ROLE_INTEL, ROLE_POLICE, ROLE_BANK (bloqué), anonyme
"""
import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.intel.models import IntelAlert, NetworkLink, ThreatZone

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_for_role(role: str) -> APIClient:
    user = User.objects.create_user(f'intel_{uuid.uuid4().hex[:6]}', password='pw')
    token = AccessToken.for_user(user)
    token['role'] = role
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
    return client


def _make_alert(**kwargs) -> IntelAlert:
    defaults = dict(
        national_id='CD-INTEL-001',
        alert_type=IntelAlert.AlertType.STRUCTURING,
        severity=IntelAlert.Severity.HIGH,
        title='Test alerte structuration',
        status=IntelAlert.Status.OPEN,
    )
    defaults.update(kwargs)
    return IntelAlert.objects.create(**defaults)


def _make_link(src: str, tgt: str, ltype='FINANCIAL', strength=0.8) -> NetworkLink:
    return NetworkLink.objects.create(
        source_national_id=src,
        target_national_id=tgt,
        link_type=ltype,
        strength=strength,
    )


def _make_zone(**kwargs) -> ThreatZone:
    defaults = dict(
        name='Zone test',
        province='Kinshasa',
        threat_type=ThreatZone.ThreatType.BANDITRY,
        severity=ThreatZone.Severity.HIGH,
        status=ThreatZone.ZoneStatus.ACTIVE,
    )
    defaults.update(kwargs)
    return ThreatZone.objects.create(**defaults)


# ── IntelAlertListCreateView ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_alert_list_200_for_intel_role():
    """ROLE_INTEL peut lister les alertes."""
    _make_alert()
    response = _client_for_role('ROLE_INTEL').get('/api/v4/intel/alerts/')
    assert response.status_code == 200
    assert response.data['count'] >= 1


@pytest.mark.django_db
def test_alert_list_200_for_police_role():
    """ROLE_POLICE peut lire les alertes (lecture seule)."""
    _make_alert()
    response = _client_for_role('ROLE_POLICE').get('/api/v4/intel/alerts/')
    assert response.status_code == 200


@pytest.mark.django_db
def test_alert_list_403_for_bank_role():
    """ROLE_BANK n'a pas accès au module Intel."""
    response = _client_for_role('ROLE_BANK').get('/api/v4/intel/alerts/')
    assert response.status_code == 403


@pytest.mark.django_db
def test_alert_list_401_anon():
    """Anonyme → 401."""
    response = APIClient().get('/api/v4/intel/alerts/')
    assert response.status_code == 401


@pytest.mark.django_db
def test_alert_list_filter_by_severity():
    """?severity= filtre les alertes par niveau."""
    _make_alert(severity='CRITICAL', title='Alerte critique')
    _make_alert(severity='LOW', title='Alerte faible')
    response = _client_for_role('ROLE_INTEL').get('/api/v4/intel/alerts/', {'severity': 'CRITICAL'})
    assert response.status_code == 200
    assert all(a['severity'] == 'CRITICAL' for a in response.data['results'])


@pytest.mark.django_db
def test_alert_create_201_for_intel():
    """ROLE_INTEL peut créer une alerte manuelle."""
    payload = {
        'national_id': 'CD-NEW-001',
        'alert_type':  'MANUAL',
        'severity':    'MEDIUM',
        'title':       'Signal faible observé',
        'evidence':    {'note': 'Activité inhabituelle détectée'},
    }
    response = _client_for_role('ROLE_INTEL').post(
        '/api/v4/intel/alerts/', payload, format='json'
    )
    assert response.status_code == 201
    assert response.data['national_id'] == 'CD-NEW-001'
    assert response.data['source_module'] == 'MANUAL'


@pytest.mark.django_db
def test_alert_create_403_for_police():
    """ROLE_POLICE ne peut pas créer d'alertes (lecture seule)."""
    payload = {'national_id': 'X', 'alert_type': 'MANUAL', 'severity': 'LOW', 'title': 'T'}
    response = _client_for_role('ROLE_POLICE').post(
        '/api/v4/intel/alerts/', payload, format='json'
    )
    assert response.status_code == 403


# ── IntelAlertDetailView ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_alert_detail_includes_evidence():
    """Le détail d'une alerte inclut les preuves brutes."""
    alert = _make_alert(evidence={'montants': [9999, 9998, 9997], 'pattern': 'structuring'})
    response = _client_for_role('ROLE_INTEL').get(f'/api/v4/intel/alerts/{alert.id}/')
    assert response.status_code == 200
    assert response.data['evidence']['pattern'] == 'structuring'


@pytest.mark.django_db
def test_alert_detail_404_unknown():
    """ID inexistant → 404."""
    response = _client_for_role('ROLE_INTEL').get('/api/v4/intel/alerts/999999/')
    assert response.status_code == 404


# ── IntelAlertStatusView ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_alert_status_patch_sets_resolved_at():
    """Clôturer une alerte remplit resolved_at automatiquement."""
    alert = _make_alert(status='OPEN')
    assert alert.resolved_at is None
    response = _client_for_role('ROLE_INTEL').patch(
        f'/api/v4/intel/alerts/{alert.id}/status/', {'status': 'CLOSED'}, format='json'
    )
    assert response.status_code == 200
    assert response.data['status'] == 'CLOSED'
    assert response.data['resolved_at'] is not None


@pytest.mark.django_db
def test_alert_status_patch_false_positive():
    """Marquer un faux positif remplit aussi resolved_at."""
    alert = _make_alert()
    response = _client_for_role('ROLE_ADMIN').patch(
        f'/api/v4/intel/alerts/{alert.id}/status/', {'status': 'FALSE_POSITIVE'}, format='json'
    )
    assert response.status_code == 200
    assert response.data['resolved_at'] is not None


# ── NetworkGraphView ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_network_graph_returns_nodes_and_edges():
    """Le graphe réseau d'un citoyen inclut nœuds et arêtes."""
    nid = 'CD-NET-001'
    _make_link(nid, 'CD-NET-002', 'FINANCIAL', 0.9)
    _make_link(nid, 'CD-NET-003', 'FAMILY', 1.0)

    response = _client_for_role('ROLE_INTEL').get(f'/api/v4/intel/network/{nid}/')
    assert response.status_code == 200
    assert response.data['national_id'] == nid
    assert response.data['total_edges'] == 2
    # Le sujet + 2 voisins = 3 nœuds
    assert response.data['total_nodes'] == 3


@pytest.mark.django_db
def test_network_graph_min_strength_filter():
    """?min_strength= filtre les liens faibles."""
    nid = 'CD-NET-004'
    _make_link(nid, 'CD-NET-005', 'TELECOM', 0.2)
    _make_link(nid, 'CD-NET-006', 'FINANCIAL', 0.9)

    response = _client_for_role('ROLE_INTEL').get(
        f'/api/v4/intel/network/{nid}/', {'min_strength': '0.5'}
    )
    assert response.status_code == 200
    assert response.data['total_edges'] == 1
    assert response.data['edges'][0]['strength'] >= 0.5


# ── NetworkLinkCreateView ─────────────────────────────────────────────────────

@pytest.mark.django_db
def test_network_link_post_creates_link():
    """POST un lien réseau crée l'enregistrement."""
    payload = {
        'source_national_id': 'CD-LNK-001',
        'target_national_id': 'CD-LNK-002',
        'link_type': 'ASSOCIATE',
        'strength': 0.7,
    }
    response = _client_for_role('ROLE_INTEL').post(
        '/api/v4/intel/network/links/', payload, format='json'
    )
    assert response.status_code == 201
    assert NetworkLink.objects.filter(
        source_national_id='CD-LNK-001', link_type='ASSOCIATE'
    ).exists()


@pytest.mark.django_db
def test_network_link_upsert():
    """POST avec le même (source, target, type) met à jour la force."""
    _make_link('CD-LNK-003', 'CD-LNK-004', 'FINANCIAL', 0.3)
    payload = {
        'source_national_id': 'CD-LNK-003',
        'target_national_id': 'CD-LNK-004',
        'link_type': 'FINANCIAL',
        'strength': 0.95,
    }
    response = _client_for_role('ROLE_INTEL').post(
        '/api/v4/intel/network/links/', payload, format='json'
    )
    assert response.status_code == 201
    assert NetworkLink.objects.filter(
        source_national_id='CD-LNK-003', strength=0.95
    ).exists()
    assert NetworkLink.objects.filter(source_national_id='CD-LNK-003').count() == 1


# ── ThreatZoneListCreateView ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_threat_zone_list_200():
    """ROLE_POLICE voit les zones actives."""
    _make_zone(province='Nord-Kivu')
    response = _client_for_role('ROLE_POLICE').get('/api/v4/intel/threats/')
    assert response.status_code == 200
    assert response.data['count'] >= 1


@pytest.mark.django_db
def test_threat_zone_create_201():
    """ROLE_INTEL peut déclarer une zone de menace."""
    payload = {
        'name':        'Zone Wangata Est',
        'province':    'Équateur',
        'territoire':  'Wangata',
        'threat_type': 'ARMED_GROUP',
        'severity':    'CRITICAL',
        'description': 'Mouvements observés depuis 3 semaines.',
        'coordinates': [[0.05, 18.25], [0.06, 18.26]],
    }
    response = _client_for_role('ROLE_INTEL').post(
        '/api/v4/intel/threats/', payload, format='json'
    )
    assert response.status_code == 201
    assert response.data['province'] == 'Équateur'
    assert ThreatZone.objects.filter(name='Zone Wangata Est').exists()


# ── IntelStatsView ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_stats_200_for_intel():
    """ROLE_INTEL accède au dashboard agrégé."""
    _make_alert(severity='CRITICAL')
    _make_zone()
    response = _client_for_role('ROLE_INTEL').get('/api/v4/intel/stats/')
    assert response.status_code == 200
    assert 'total_alerts' in response.data
    assert 'active_threat_zones' in response.data
    assert response.data['critical_alerts'] >= 1


@pytest.mark.django_db
def test_stats_403_for_police():
    """ROLE_POLICE n'a pas accès aux stats (lecture seule)."""
    response = _client_for_role('ROLE_POLICE').get('/api/v4/intel/stats/')
    assert response.status_code == 403
