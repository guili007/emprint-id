from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Citizen
from .serializers import CitizenSerializer


class CitizenListView(generics.ListCreateAPIView):
    queryset = Citizen.objects.filter(is_active=True).select_related('province', 'commune')
    serializer_class = CitizenSerializer


class CitizenDetailView(generics.RetrieveUpdateAPIView):
    queryset = Citizen.objects.all()
    serializer_class = CitizenSerializer


class QRVerifyView(APIView):
    """POST /api/v1/verify/qr/ — vérification par QR code (sans biométrie).
    L'endpoint biométrique complet est en /api/v2/verify/."""

    def post(self, request):
        national_id = request.data.get('national_id', '').strip().upper()
        if not national_id:
            return Response({'error': 'national_id requis'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            citizen = Citizen.objects.select_related('province', 'commune').get(
                national_id=national_id, is_active=True
            )
        except Citizen.DoesNotExist:
            return Response({'status': 'REJECTED', 'reason': 'Identifiant inconnu ou inactif'},
                            status=status.HTTP_404_NOT_FOUND)

        return Response({
            'status': 'VERIFIED',
            'national_id': citizen.national_id,
            'full_name': citizen.nom_complet,
            'dob': citizen.date_naissance,
            'province': citizen.province.nom if citizen.province else None,
            'commune': citizen.commune.nom if citizen.commune else None,
            'issued_at': citizen.issued_at,
        })
