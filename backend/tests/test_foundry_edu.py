"""
Tests Foundry Edu — dossiers scolaires EduFirst (cache local).

Couvre :
  - EduStudentListView     : liste + filtres (?school_id, ?annee, ?linked_only, ?q)
  - EduStudentByNationalIdView : dossier complet par national_id
  - EduStudentByMatriculeView  : dossier par matricule EduFirst
  - EduSchoolListView      : liste des écoles synchronisées
  - EduStatsView           : statistiques agrégées (admin uniquement)
  - RBAC                   : ROLE_EDU (reader), ROLE_ADMIN, ROLE_BANK (bloqué)
"""
import uuid
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.foundry.models import (
    EduSchool, EduStudent, EduBulletin, EduNoteBulletin,
)

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_for_role(role: str) -> APIClient:
    """Crée un APIClient authentifié avec le rôle JWT donné."""
    user = User.objects.create_user(f'edu_{uuid.uuid4().hex[:6]}', password='pw')
    token = AccessToken.for_user(user)
    token['role'] = role
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token)}')
    return client


def _make_school(**kwargs) -> EduSchool:
    """Crée une EduSchool en base."""
    defaults = dict(
        edufirst_school_id=abs(hash(uuid.uuid4().hex)) % 100000,
        name=f"Lycée-{uuid.uuid4().hex[:4]}",
        country='CD',
        city='Kinshasa',
    )
    defaults.update(kwargs)
    return EduSchool.objects.create(**defaults)


def _make_student(school, **kwargs) -> EduStudent:
    """Crée un EduStudent en base."""
    defaults = dict(
        edufirst_student_id=abs(hash(uuid.uuid4().hex)) % 100000,
        school=school,
        matricule=f"KIN-{uuid.uuid4().hex[:4].upper()}",
        nom='Kabila',
        prenom='Jean',
        date_naissance=date(2005, 3, 15),
    )
    defaults.update(kwargs)
    return EduStudent.objects.create(**defaults)


def _make_bulletin(student, **kwargs) -> EduBulletin:
    """Crée un EduBulletin en base."""
    defaults = dict(
        edufirst_bulletin_id=abs(hash(uuid.uuid4().hex)) % 100000,
        student=student,
        periode='1er trimestre',
        annee_scolaire='2025-2026',
        moyenne='14.50',
        mention='C',
    )
    defaults.update(kwargs)
    return EduBulletin.objects.create(**defaults)


# ── Student List ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_student_list_200_for_edu_role():
    """ROLE_EDU peut lister les élèves."""
    school = _make_school()
    _make_student(school)
    client = _client_for_role('ROLE_EDU')
    response = client.get('/api/v3/foundry/edu/students/')
    assert response.status_code == 200
    assert response.data['count'] >= 1


@pytest.mark.django_db
def test_student_list_403_for_bank_role():
    """ROLE_BANK n'a pas accès au secteur EDU."""
    client = _client_for_role('ROLE_BANK')
    response = client.get('/api/v3/foundry/edu/students/')
    assert response.status_code == 403


@pytest.mark.django_db
def test_student_list_401_for_anon():
    """Anonyme → 401."""
    response = APIClient().get('/api/v3/foundry/edu/students/')
    assert response.status_code == 401


@pytest.mark.django_db
def test_student_list_filter_by_annee():
    """Le filtre ?annee= ne retourne que les élèves ayant un bulletin pour cette année."""
    school = _make_school()
    s1 = _make_student(school)
    s2 = _make_student(school)
    _make_bulletin(s1, annee_scolaire='2025-2026')
    _make_bulletin(s2, annee_scolaire='2024-2025')

    client = _client_for_role('ROLE_EDU')
    response = client.get('/api/v3/foundry/edu/students/', {'annee': '2025-2026'})

    assert response.status_code == 200
    ids = [r['id'] for r in response.data['results']]
    assert s1.id in ids
    assert s2.id not in ids


@pytest.mark.django_db
def test_student_list_linked_only():
    """?linked_only=true ne retourne que les élèves liés à un national_id."""
    school = _make_school()
    linked   = _make_student(school, national_id='CD12345678')
    unlinked = _make_student(school, national_id=None)

    client = _client_for_role('ROLE_EDU')
    response = client.get('/api/v3/foundry/edu/students/', {'linked_only': 'true'})

    assert response.status_code == 200
    ids = [r['id'] for r in response.data['results']]
    assert linked.id in ids
    assert unlinked.id not in ids


@pytest.mark.django_db
def test_student_list_search_by_nom():
    """?q= filtre par nom ou prénom."""
    school = _make_school()
    _make_student(school, nom='Mukendi', prenom='Paul')
    _make_student(school, nom='Tshisekedi', prenom='Marie')

    client = _client_for_role('ROLE_EDU')
    response = client.get('/api/v3/foundry/edu/students/', {'q': 'Mukendi'})

    assert response.status_code == 200
    for s in response.data['results']:
        assert 'mukendi' in (s['nom'] + s['prenom']).lower()


# ── Student Detail by national_id ─────────────────────────────────────────────

@pytest.mark.django_db
def test_student_detail_by_national_id_includes_bulletins():
    """Le dossier complet inclut les bulletins avec les notes."""
    school  = _make_school()
    student = _make_student(school, national_id='CD87654321')
    bulletin = _make_bulletin(student)
    EduNoteBulletin.objects.create(
        bulletin=bulletin, matiere_nom='Mathématiques',
        note='16.00', note_max='20', appreciation='Très bien',
    )

    client = _client_for_role('ROLE_EDU')
    response = client.get(f'/api/v3/foundry/edu/students/{student.national_id}/')

    assert response.status_code == 200
    assert response.data['nom'] == 'Kabila'
    assert len(response.data['bulletins']) == 1
    assert response.data['bulletins'][0]['moyenne'] == '14.50'
    assert len(response.data['bulletins'][0]['notes']) == 1
    assert response.data['bulletins'][0]['notes'][0]['matiere_nom'] == 'Mathématiques'


@pytest.mark.django_db
def test_student_detail_404_when_no_national_id_link():
    """national_id inconnu ou non lié → 404."""
    client = _client_for_role('ROLE_EDU')
    response = client.get('/api/v3/foundry/edu/students/CD_INCONNU/')
    assert response.status_code == 404


# ── Student Detail by matricule ───────────────────────────────────────────────

@pytest.mark.django_db
def test_student_by_matricule_200():
    """Recherche par matricule EduFirst retourne le dossier."""
    school  = _make_school()
    student = _make_student(school, matricule='KIN-ABCD')

    client = _client_for_role('ROLE_EDU')
    response = client.get('/api/v3/foundry/edu/students/by-matricule/KIN-ABCD/')
    assert response.status_code == 200
    assert response.data['matricule'] == 'KIN-ABCD'


@pytest.mark.django_db
def test_student_by_matricule_404():
    """Matricule inexistant → 404."""
    client = _client_for_role('ROLE_EDU')
    response = client.get('/api/v3/foundry/edu/students/by-matricule/INEXISTANT/')
    assert response.status_code == 404


# ── Schools ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_school_list_200_for_edu_role():
    """ROLE_EDU peut lister les écoles."""
    _make_school(name='Lycée Bosangani', country='CD')
    client = _client_for_role('ROLE_EDU')
    response = client.get('/api/v3/foundry/edu/schools/')
    assert response.status_code == 200
    assert response.data['count'] >= 1


# ── Stats ─────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_stats_403_for_edu_role():
    """ROLE_EDU n'a pas accès aux stats (admin seulement)."""
    client = _client_for_role('ROLE_EDU')
    response = client.get('/api/v3/foundry/edu/stats/')
    assert response.status_code == 403


@pytest.mark.django_db
def test_stats_200_for_admin():
    """ROLE_ADMIN peut accéder aux stats agrégées."""
    school  = _make_school()
    student = _make_student(school, national_id='CD11111111')
    _make_bulletin(student, mention='B', moyenne='15.00')

    client = _client_for_role('ROLE_ADMIN')
    response = client.get('/api/v3/foundry/edu/stats/')

    assert response.status_code == 200
    assert response.data['total_students'] >= 1
    assert response.data['linked_students'] >= 1
    assert response.data['total_bulletins'] >= 1
    assert 'bulletins_by_mention' in response.data
    assert 'sync_status' in response.data
