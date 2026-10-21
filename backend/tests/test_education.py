"""
Tests Module 10 — Eyeshield Education.

16 tests couvrant :
  - Accès par rôle (200 / 403 / 401)
  - CRUD dossiers, résultats, diplômes, alertes
  - Profil étudiant complet
  - Unicité du numéro de certificat (anti-fraude)
  - Stats agrégées
  - academic_risk_score (TODO(human) — skippé jusqu'à implémentation)
"""
import pytest
from rest_framework.test import APIClient

from apps.education.models import AcademicResult, Diploma, SchoolAlert, StudentRecord
from apps.education.views import academic_risk_score


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_user(role):
    class FakeUser:
        is_authenticated = True
        pk = 1
        def __init__(self, r): self.role = r
    return FakeUser(role)


def auth_client(role):
    client = APIClient()
    client.force_authenticate(user=make_user(role))
    return client


@pytest.fixture
def edu_client():
    return auth_client('ROLE_EDU')


@pytest.fixture
def admin_client():
    return auth_client('ROLE_ADMIN')


@pytest.fixture
def bank_client():
    return auth_client('ROLE_BANK')


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def student(db):
    return StudentRecord.objects.create(
        national_id='CD-EDU-001', school_year='2023-2024',
        niveau='SECONDAIRE', classe='5ème secondaire',
        etablissement='Lycée de Kinshasa', province='Kinshasa',
    )


# ── Tests accès ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_student_list_200_for_edu_role(edu_client):
    resp = edu_client.get('/api/v10/education/students/')
    assert resp.status_code == 200


@pytest.mark.django_db
def test_student_list_403_for_bank_role(bank_client):
    resp = bank_client.get('/api/v10/education/students/')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_student_list_401_for_anon(anon_client):
    resp = anon_client.get('/api/v10/education/students/')
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_stats_403_for_edu_worker(edu_client):
    resp = edu_client.get('/api/v10/education/stats/')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_stats_200_for_admin(admin_client):
    resp = admin_client.get('/api/v10/education/stats/')
    assert resp.status_code == 200


# ── Tests dossiers scolaires ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_create_student_record(edu_client):
    payload = {
        'national_id': 'CD-EDU-999',
        'school_year': '2024-2025',
        'niveau': 'PRIMAIRE',
        'classe': '6ème primaire',
        'etablissement': 'EP Gombe',
        'province': 'Kinshasa',
    }
    resp = edu_client.post('/api/v10/education/students/', payload, format='json')
    assert resp.status_code == 201
    assert resp.data['national_id'] == 'CD-EDU-999'


@pytest.mark.django_db
def test_student_detail_includes_results_and_diplomas(edu_client, student):
    AcademicResult.objects.create(
        student=student, matiere='Mathématiques',
        note=75, note_max=100, mention='DISTINCTION',
    )
    resp = edu_client.get(f'/api/v10/education/students/{student.national_id}/')
    assert resp.status_code == 200
    assert len(resp.data['records'][0]['results']) == 1


@pytest.mark.django_db
def test_student_detail_404_unknown(edu_client):
    resp = edu_client.get('/api/v10/education/students/INCONNU-ZZZ/')
    assert resp.status_code == 404


@pytest.mark.django_db
def test_duplicate_student_record_same_year_returns_400(edu_client, student):
    payload = {
        'national_id': student.national_id,
        'school_year': student.school_year,  # même année → conflit
        'niveau': 'SECONDAIRE', 'classe': '5ème', 'etablissement': 'Test', 'province': 'Kinshasa',
    }
    resp = edu_client.post('/api/v10/education/students/', payload, format='json')
    assert resp.status_code == 400


# ── Tests résultats ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_post_result_creates_record(edu_client, student):
    payload = {
        'student': student.pk,
        'matiere': 'Français',
        'note': '62.5',
        'note_max': '100',
        'mention': 'SATISFACTION',
    }
    resp = edu_client.post('/api/v10/education/results/', payload, format='json')
    assert resp.status_code == 201
    assert AcademicResult.objects.filter(student=student, matiere='Français').exists()


# ── Tests diplômes ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_create_diploma(edu_client):
    payload = {
        'national_id': 'CD-EDU-001',
        'type_diplome': 'DIPL_ETAT',
        'etablissement': 'Lycée de Kinshasa',
        'province': 'Kinshasa',
        'annee_obtention': 2023,
        'numero_certificat': 'KIN-2023-00001',
        'mention': 'DISTINCTION',
    }
    resp = edu_client.post('/api/v10/education/diplomas/', payload, format='json')
    assert resp.status_code == 201
    assert resp.data['numero_certificat'] == 'KIN-2023-00001'


@pytest.mark.django_db
def test_duplicate_numero_certificat_returns_400(edu_client, db):
    """Anti-fraude : deux diplômes avec le même numéro de certificat sont refusés."""
    Diploma.objects.create(
        national_id='CD-A', type_diplome='DIPL_ETAT',
        etablissement='Lycée', province='Kinshasa',
        annee_obtention=2022, numero_certificat='KIN-UNIQUE-001',
    )
    payload = {
        'national_id': 'CD-B', 'type_diplome': 'DIPL_ETAT',
        'etablissement': 'Autre lycée', 'province': 'Kinshasa',
        'annee_obtention': 2023, 'numero_certificat': 'KIN-UNIQUE-001',
    }
    resp = edu_client.post('/api/v10/education/diplomas/', payload, format='json')
    assert resp.status_code == 400


# ── Tests alertes ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_create_school_alert(edu_client):
    payload = {
        'national_id': 'CD-EDU-001',
        'alert_type': 'ABANDON',
        'severity': 'ELEVE',
        'description': 'Absences répétées depuis 3 semaines.',
    }
    resp = edu_client.post('/api/v10/education/alerts/', payload, format='json')
    assert resp.status_code == 201
    assert resp.data['alert_type'] == 'ABANDON'


@pytest.mark.django_db
def test_alert_filter_by_statut(edu_client, db):
    SchoolAlert.objects.create(
        national_id='CD-EDU-001', alert_type='VULNERABLE',
        severity='MODERE', description='Situation familiale précaire', statut='OUVERT',
    )
    resp = edu_client.get('/api/v10/education/alerts/?statut=OUVERT')
    assert resp.status_code == 200
    assert len(resp.data) >= 1


# ── Tests stats ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_stats_returns_aggregates(admin_client, db):
    resp = admin_client.get('/api/v10/education/stats/')
    assert resp.status_code == 200
    assert 'students' in resp.data
    assert 'diplomas' in resp.data
    assert 'alerts' in resp.data


# ── Test academic_risk_score (TODO(human)) ─────────────────────────────────────

@pytest.mark.django_db
def test_academic_risk_score_skipped_until_implemented(db):
    result = academic_risk_score('CD-TEST-EDU')
    if result is None:
        pytest.skip("academic_risk_score() pas encore implémentée — TODO(human)")
    assert 'score' in result
    assert 'level' in result
    assert result['score'] >= 0
    assert result['score'] <= 100
