from django.urls import path
from . import views

urlpatterns = [
    path('citizens/search/', views.CitizenSearchView.as_view(), name='data-citizen-search'),
    path('logs/', views.LogsView.as_view(), name='data-logs'),
    path('stats/', views.StatsView.as_view(), name='data-stats'),
]
