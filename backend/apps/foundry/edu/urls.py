"""URLs Foundry Edu — sous-ensemble /api/v3/foundry/edu/."""
from django.urls import path

from .views import (
    EduStudentListView,
    EduStudentByNationalIdView,
    EduStudentByMatriculeView,
    EduSchoolListView,
    EduStatsView,
)

urlpatterns = [
    # Dossiers étudiants
    path('students/', EduStudentListView.as_view(), name='edu-student-list'),
    # ⚠ by-matricule DOIT être avant <str:national_id> : Django matche dans l'ordre
    path('students/by-matricule/<str:matricule>/', EduStudentByMatriculeView.as_view(), name='edu-student-by-matricule'),
    path('students/<str:national_id>/',            EduStudentByNationalIdView.as_view(), name='edu-student-detail'),

    # Écoles synchronisées
    path('schools/',  EduSchoolListView.as_view(), name='edu-school-list'),

    # Dashboard admin
    path('stats/',    EduStatsView.as_view(),      name='edu-stats'),
]
