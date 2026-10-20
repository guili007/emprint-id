"""
Endpoints biométriques v2.

POST /api/v2/verify/            → vérification face + liveness + watchlist
GET  /api/v2/watchlist/check/<citizen_id>/  → vérification watchlist par ID
POST /api/v2/watchlist/         → ajout (WATCHLIST_ADMIN seulement)
DELETE /api/v2/watchlist/<id>/  → désactivation (WATCHLIST_ADMIN seulement)
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.citizens.models import Citizen
from config.signing import sign_response as _sign_response
from .exceptions import FaceNotFound, LivenessDetectionFailed, WatchlistHit
from .models import VerificationLog, WatchlistEntry
from .permissions import IsFieldAgent, IsWatchlistAdmin
from .serializers import FaceVerifySerializer, WatchlistEntrySerializer
from .services import BiometricService

_service = BiometricService()


class FaceVerifyView(APIView):
    """
    POST /api/v2/verify/

    Vérification biométrique complète :
    image base64 → liveness → ArcFace 1:N → watchlist → réponse signée HMAC.

    Throttle : 10 req/min par token (règle sécurité §10.6).
    """
    permission_classes = [IsFieldAgent]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        serializer = FaceVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        image_bytes: bytes = serializer.validated_data['image']
        agent_role = getattr(request.user, 'role', '')

        try:
            result = _service.verify(
                image_bytes=image_bytes,
                requesting_user_id=request.user.pk,
                agent_role=agent_role,
            )
        except FaceNotFound as e:
            return Response(
                _sign_response({'status': 'REJECTED', 'reason': str(e)}),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        except LivenessDetectionFailed as e:
            return Response(
                _sign_response({'status': 'LIVENESS_FAILED', 'reason': str(e)}),
                status=status.HTTP_403_FORBIDDEN
            )
        except WatchlistHit as e:
            return Response(
                _sign_response({
                    'status': 'WATCHLIST_HIT',
                    'alert_level': e.alert_level,
                    'reason': e.reason,
                }),
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                _sign_response({'status': 'ERROR', 'reason': 'Erreur interne'}),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if result.status == VerificationLog.VerifStatus.VERIFIED:
            c = result.citizen
            payload = {
                'status': 'VERIFIED',
                'national_id': c.national_id,
                'full_name': c.nom_complet,
                'dob': c.date_naissance,
                'province': c.province.nom if c.province else None,
                'commune': c.commune.nom if c.commune else None,
                'confidence': round(result.confidence_score, 4) if result.confidence_score else None,
                'issued_at': c.issued_at,
                'timestamp': timezone.now(),
            }
            return Response(_sign_response(payload), status=status.HTTP_200_OK)

        return Response(
            _sign_response({'status': result.status, 'message': result.message}),
            status=status.HTTP_200_OK
        )


class WatchlistCheckView(APIView):
    """GET /api/v2/watchlist/check/<citizen_id>/ — vérification rapide."""
    permission_classes = [IsFieldAgent]

    def get(self, request, citizen_id):
        from django.db.models import Case, IntegerField, Q, When
        citizen = get_object_or_404(Citizen, id=citizen_id, is_active=True)
        entry = (
            WatchlistEntry.objects
            .filter(citizen=citizen, is_active=True)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .order_by(
                Case(
                    When(alert_level='ROUGE', then=0),
                    When(alert_level='ORANGE', then=1),
                    When(alert_level='JAUNE', then=2),
                    default=3,
                    output_field=IntegerField(),
                )
            )
            .first()
        )
        if entry:
            return Response(_sign_response({
                'on_watchlist': True,
                'alert_level': entry.alert_level,
                'issued_by': entry.issued_by,
            }))
        return Response(_sign_response({'on_watchlist': False}))


class WatchlistView(APIView):
    """
    POST /api/v2/watchlist/ — ajout (WATCHLIST_ADMIN seulement)
    """
    permission_classes = [IsWatchlistAdmin]

    def post(self, request):
        serializer = WatchlistEntrySerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        entry = serializer.save()
        return Response(WatchlistEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class WatchlistDeactivateView(APIView):
    """DELETE /api/v2/watchlist/<id>/ — désactivation (pas de vrai DELETE)."""
    permission_classes = [IsWatchlistAdmin]

    def delete(self, request, pk):
        entry = get_object_or_404(WatchlistEntry, pk=pk)
        entry.is_active = False
        entry.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TestAlertView(APIView):
    """POST /api/v2/test-alert/ — déclenche une fausse alerte watchlist (DEV uniquement)."""
    permission_classes = [IsFieldAgent]

    def post(self, request):
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        authority = request.data.get('authority', 'CIVIL')
        groups = {
            'CIVIL':     ['security_dashboard'],
            'MILITAIRE': ['military_dashboard'],
            'ETAT':      ['security_dashboard', 'military_dashboard'],
        }.get(authority, ['security_dashboard'])

        payload = {
            'type': 'watchlist_alert',
            'alert_level': request.data.get('alert_level', 'ROUGE'),
            'authority': authority,
            'national_id': request.data.get('national_id', 'CG-KN-LWA-000147-X9'),
            'reason': request.data.get('reason', 'SIMULATION TEST'),
            'issued_by': 'Système de test',
            'agent_id': request.user.pk,
        }

        channel_layer = get_channel_layer()
        send = async_to_sync(channel_layer.group_send)
        for group in groups:
            send(group, payload)

        return Response({'sent': True, 'groups': groups})
