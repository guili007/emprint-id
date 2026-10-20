import base64
from rest_framework import serializers
from .models import WatchlistEntry, VerificationLog


class FaceVerifySerializer(serializers.Serializer):
    """Corps de la requête POST /api/v2/verify/."""
    image = serializers.CharField(
        help_text="Image du visage encodée en base64 (JPEG ou PNG, max 5 Mo)"
    )

    def validate_image(self, value: str) -> bytes:
        try:
            image_bytes = base64.b64decode(value)
        except Exception:
            raise serializers.ValidationError("Image invalide — encodage base64 attendu.")
        if len(image_bytes) > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image trop lourde (max 5 Mo).")
        if not (image_bytes.startswith(b'\xff\xd8\xff') or image_bytes.startswith(b'\x89PNG')):
            raise serializers.ValidationError("Format invalide — JPEG ou PNG attendu.")
        return image_bytes


class WatchlistEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = WatchlistEntry
        fields = [
            'id', 'citizen', 'alert_level', 'authority', 'reason',
            'issued_by', 'issued_at', 'expires_at', 'is_active',
        ]
        read_only_fields = ['id', 'issued_at', 'created_by']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class VerificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationLog
        fields = [
            'id', 'citizen', 'status', 'confidence_score',
            'liveness_score', 'agent_role', 'timestamp',
        ]
        read_only_fields = fields
