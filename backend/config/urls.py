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

    # v3/data — Module 02 Eyeshield Data : couche ontologie (liens inter-sources)
    path('api/v3/data/', include('apps.data.ontology_urls')),

    # v3/foundry — Module 03 Eyeshield Foundry (KYC bancaire + fraude)
    path('api/v3/foundry/', include('apps.foundry.urls')),

    # v4/intel — Module 04 Eyeshield Intel (renseignement + graphe + menaces)
    path('api/v4/intel/', include('apps.intel.urls')),

    # v5/audit — Module 05 Eyeshield Audit (trail immuable + conformité)
    path('api/v5/audit/', include('apps.audit.urls')),

    # v6/comms — Module 06 Eyeshield Comms (SIM/IMEI + CDR + corrélation)
    path('api/v6/comms/', include('apps.comms.urls')),

    # v7/field — Module 07 Eyeshield Field (agents terrain + sync différée)
    path('api/v7/field/', include('apps.field.urls')),

    # v8/justice — Module 08 Eyeshield Justice (casier + mandats + alertes judiciaires)
    path('api/v8/justice/', include('apps.justice.urls')),

    # v9/health — Module 09 Eyeshield Health (dossiers médicaux + épidémio)
    path('api/v9/health/', include('apps.health.urls')),

    # v10/education — Module 10 Eyeshield Education (registre scolaire national)
    path('api/v10/education/', include('apps.education.urls')),
]
