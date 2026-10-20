from django.urls import path

from .views import (
    CallRecordListCreateView,
    CommsAlertListCreateView,
    CommsStatsView,
    SimCardListCreateView,
    SimCardProfileView,
)

urlpatterns = [
    path('sims/',                       SimCardListCreateView.as_view(),  name='comms-sims'),
    path('sims/<str:national_id>/profile/', SimCardProfileView.as_view(), name='comms-sim-profile'),
    path('records/',                    CallRecordListCreateView.as_view(), name='comms-records'),
    path('alerts/',                     CommsAlertListCreateView.as_view(), name='comms-alerts'),
    path('stats/',                      CommsStatsView.as_view(),          name='comms-stats'),
]
