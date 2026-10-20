"""URLs Module 07 — Eyeshield Field."""
from django.urls import path

from .views import (
    FieldAgentListView,
    FieldMissionDetailView,
    FieldMissionListCreateView,
    FieldRecordListView,
    FieldStatsView,
    FieldSyncView,
)

urlpatterns = [
    path('agents/',            FieldAgentListView.as_view(),          name='field-agent-list'),
    path('missions/',          FieldMissionListCreateView.as_view(),   name='field-mission-list'),
    path('missions/<int:pk>/', FieldMissionDetailView.as_view(),       name='field-mission-detail'),
    path('sync/',              FieldSyncView.as_view(),                name='field-sync'),
    path('records/',           FieldRecordListView.as_view(),          name='field-record-list'),
    path('stats/',             FieldStatsView.as_view(),               name='field-stats'),
]
