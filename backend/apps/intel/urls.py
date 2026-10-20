"""URLs Module 04 — Eyeshield Intel (/api/v4/intel/)."""
from django.urls import path

from . import views

urlpatterns = [
    # Alertes
    path('alerts/',              views.IntelAlertListCreateView.as_view(), name='intel-alert-list'),
    path('alerts/<int:pk>/',     views.IntelAlertDetailView.as_view(),     name='intel-alert-detail'),
    path('alerts/<int:pk>/status/', views.IntelAlertStatusView.as_view(), name='intel-alert-status'),

    # Graphe réseau
    # ⚠ 'network/links/' doit être avant 'network/<str:national_id>/' (ordre Django)
    path('network/links/',                    views.NetworkLinkCreateView.as_view(), name='intel-network-link-create'),
    path('network/<str:national_id>/',        views.NetworkGraphView.as_view(),      name='intel-network-graph'),

    # Zones de menace
    path('threats/',             views.ThreatZoneListCreateView.as_view(), name='intel-threats'),

    # Dashboard
    path('stats/',               views.IntelStatsView.as_view(),           name='intel-stats'),
]
