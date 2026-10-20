from django.urls import path
from . import views

urlpatterns = [
    path('citizens/', views.CitizenListView.as_view(), name='citizen-list'),
    path('citizens/<uuid:pk>/', views.CitizenDetailView.as_view(), name='citizen-detail'),
    path('verify/qr/', views.QRVerifyView.as_view(), name='verify-qr'),
]
