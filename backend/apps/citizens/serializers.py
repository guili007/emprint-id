from rest_framework import serializers
from .models import Citizen


class CitizenSerializer(serializers.ModelSerializer):
    nom_complet = serializers.ReadOnlyField()

    class Meta:
        model = Citizen
        fields = [
            'id', 'national_id', 'nom', 'postnom', 'prenom',
            'nom_complet', 'sexe', 'date_naissance', 'lieu_naissance',
            'province', 'commune', 'issued_at', 'is_active',
        ]
        read_only_fields = ['id', 'national_id', 'issued_at']
