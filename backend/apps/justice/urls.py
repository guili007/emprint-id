"""URLs Module 08 — Eyeshield Justice."""
from django.urls import path

from .views import (
    ArrestWarrantListCreateView,
    ArrestWarrantStatusView,
    CriminalProfileView,
    CriminalRecordListCreateView,
    JusticeAlertListCreateView,
    JusticeStatsView,
)

urlpatterns = [
    path('records/',                        CriminalRecordListCreateView.as_view(), name='justice-record-list'),
    path('records/<str:national_id>/profile/', CriminalProfileView.as_view(),      name='justice-profile'),
    path('warrants/',                       ArrestWarrantListCreateView.as_view(),  name='justice-warrant-list'),
    path('warrants/<int:pk>/status/',       ArrestWarrantStatusView.as_view(),      name='justice-warrant-status'),
    path('alerts/',                         JusticeAlertListCreateView.as_view(),   name='justice-alert-list'),
    path('stats/',                          JusticeStatsView.as_view(),             name='justice-stats'),
]
