"""URLs Module 10 — Eyeshield Education (v10/education/)."""
from django.urls import path

from .views import (
    AcademicResultCreateView,
    DiplomaListCreateView,
    SchoolAlertListCreateView,
    StudentProfileView,
    StudentRecordListCreateView,
    EducationStatsView,
)

urlpatterns = [
    path('students/',                      StudentRecordListCreateView.as_view(), name='edu-student-list'),
    path('students/<str:national_id>/',    StudentProfileView.as_view(),          name='edu-student-detail'),
    path('results/',                       AcademicResultCreateView.as_view(),    name='edu-result-create'),
    path('diplomas/',                      DiplomaListCreateView.as_view(),       name='edu-diploma-list'),
    path('alerts/',                        SchoolAlertListCreateView.as_view(),   name='edu-alert-list'),
    path('stats/',                         EducationStatsView.as_view(),          name='edu-stats'),
]
