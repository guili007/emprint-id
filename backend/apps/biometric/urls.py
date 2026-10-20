from django.urls import path
from . import views

urlpatterns = [
    path('verify/', views.FaceVerifyView.as_view(), name='biometric-verify'),
    path('watchlist/', views.WatchlistView.as_view(), name='watchlist-list'),
    path('watchlist/check/<uuid:citizen_id>/', views.WatchlistCheckView.as_view(), name='watchlist-check'),
    path('watchlist/<int:pk>/', views.WatchlistDeactivateView.as_view(), name='watchlist-deactivate'),
    path('test-alert/', views.TestAlertView.as_view(), name='test-alert'),
]
