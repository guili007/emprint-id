from django.urls import path

from .views import (
    AuditEventListView,
    AuditReportDetailView,
    AuditReportListCreateView,
    AuditStatsView,
    ComplianceFlagListView,
    ComplianceFlagStatusView,
)

urlpatterns = [
    path('events/',             AuditEventListView.as_view(),         name='audit-events'),
    path('stats/',              AuditStatsView.as_view(),             name='audit-stats'),
    path('flags/',              ComplianceFlagListView.as_view(),      name='audit-flags'),
    path('flags/<int:pk>/status/', ComplianceFlagStatusView.as_view(), name='audit-flag-status'),
    path('reports/',            AuditReportListCreateView.as_view(),  name='audit-reports'),
    path('reports/<int:pk>/',   AuditReportDetailView.as_view(),      name='audit-report-detail'),
]
