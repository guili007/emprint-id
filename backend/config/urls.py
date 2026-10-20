from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from config.auth import RoleTokenObtainPairSerializer

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth JWT (avec claim `role`)
    path('api/token/', TokenObtainPairView.as_view(serializer_class=RoleTokenObtainPairSerializer), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # v1 — identité (QR, cartes)
    path('api/v1/', include('apps.citizens.urls')),

    # v2 — biométrie (face + watchlist)
    path('api/v2/', include('apps.biometric.urls')),

    # v2/data — Module 02 Eyeshield Data (recherche unifiée + analytics + logs)
    path('api/v2/data/', include('apps.data.urls')),
]
