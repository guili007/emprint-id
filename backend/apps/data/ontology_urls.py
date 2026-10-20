"""URLs ontologie Module 02 — sous /api/v3/data/."""
from django.urls import path

from . import views

urlpatterns = [
    # Sources de données disponibles (filtrées par rôle)
    path('sources/', views.DataSourceListView.as_view(), name='data-sources'),

    # Profil ontologique unifié d'un citoyen
    path(
        'citizens/<str:national_id>/profile/',
        views.CitizenProfileView.as_view(),
        name='data-citizen-profile',
    ),

    # Liens (POST = upsert admin, GET via CitizenLinksView)
    path('links/', views.DataLinkListCreateView.as_view(), name='data-links'),
    path(
        'links/<str:national_id>/',
        views.CitizenLinksView.as_view(),
        name='data-citizen-links',
    ),

    # Statistiques de couverture (admin)
    path('ontology/stats/', views.OntologyStatsView.as_view(), name='data-ontology-stats'),
]
