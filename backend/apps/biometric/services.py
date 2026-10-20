"""
BiometricService — DeepFace + ArcFace + pgvector.

Flux de vérification :
  1. Valider l'image reçue (taille, format, visage détectable)
  2. Vérifier la liveness (anti_spoofing=True, TOUJOURS)
  3. Extraire l'embedding ArcFace 512D
  4. Recherche 1:N dans pgvector (cosine similarity > threshold)
  5. Vérifier la watchlist
  6. Retourner le résultat + logger l'accès

Règles absolues respectées ici :
  - anti_spoofing n'est jamais désactivé
  - Aucune image ni embedding dans les logs
  - Tout accès est loggé dans VerificationLog
"""
import io
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Optional

import numpy as np
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.citizens.models import Citizen
from .exceptions import FaceNotFound, LivenessDetectionFailed, NoEmbeddingRegistered, WatchlistHit
from .models import CitizenFaceEmbedding, VerificationLog, WatchlistEntry

logger = logging.getLogger('emprint.biometric')


@dataclass
class VerificationResult:
    status: str                        # VerificationLog.VerifStatus value
    citizen: Optional[Citizen]
    confidence_score: Optional[float]
    liveness_score: Optional[float]
    watchlist_entry: Optional[WatchlistEntry]
    message: str


class BiometricService:
    """
    Encapsule toutes les opérations biométriques.
    Une seule instance suffit (stateless — DeepFace charge les modèles une fois).
    """

    SIMILARITY_THRESHOLD: float = settings.FACE_SIMILARITY_THRESHOLD   # 0.85
    LIVENESS_THRESHOLD: float = settings.LIVENESS_THRESHOLD             # 0.7
    MODEL_NAME = 'ArcFace'
    DETECTOR = 'retinaface'

    # ─────────────────────────────────────────────
    # API publique
    # ─────────────────────────────────────────────

    def verify(
        self,
        image_bytes: bytes,
        requesting_user_id: int,
        agent_role: str = '',
    ) -> VerificationResult:
        """
        Vérification biométrique complète 1:N.

        Ordre strict (sécurité) :
          1. Liveness → si échec : log REJECTED_LIVENESS + raise LivenessDetectionFailed
          2. Embedding ArcFace → si pas de visage : log REJECTED_FACE + raise FaceNotFound
          3. Recherche 1:N pgvector → si pas de match : log REJECTED_FACE + return
          4. Watchlist → si hit : alerte silencieuse WebSocket + log + raise WatchlistHit
          5. OK → log VERIFIED + return

        Les erreurs techniques (DeepFace plante, DB timeout) : log ERROR + return
        sans propager l'exception — le service reste en ligne.
        """
        citizen = None
        liveness_score = None

        try:
            # ── 1 & 2 : Liveness + Embedding ──────────────────────────────
            try:
                embedding, liveness_score, quality_score = self._extract_embedding(image_bytes)
            except FaceNotFound:
                # Pas de visage détecté — on log et on propage pour la vue
                self._log(
                    VerificationLog.VerifStatus.REJECTED_FACE,
                    agent_user_id=requesting_user_id,
                    agent_role=agent_role,
                )
                raise
            except LivenessDetectionFailed:
                # Tentative de fraude potentielle — on log TOUJOURS (règle §10.7)
                self._log(
                    VerificationLog.VerifStatus.REJECTED_LIVENESS,
                    agent_user_id=requesting_user_id,
                    agent_role=agent_role,
                    liveness=liveness_score,
                )
                raise

            # ── 3 : Recherche 1:N pgvector ────────────────────────────────
            match = self._search_1n(embedding)
            if match is None:
                self._log(
                    VerificationLog.VerifStatus.REJECTED_FACE,
                    agent_user_id=requesting_user_id,
                    agent_role=agent_role,
                    liveness=liveness_score,
                )
                return VerificationResult(
                    status=VerificationLog.VerifStatus.REJECTED_FACE,
                    citizen=None,
                    confidence_score=None,
                    liveness_score=liveness_score,
                    watchlist_entry=None,
                    message="Identité non reconnue.",
                )

            citizen, confidence = match

            # ── 4 : Watchlist — protocole Silent Flagging ─────────────────
            watchlist_entry = self._check_watchlist(citizen)
            if watchlist_entry:
                # Alerte silencieuse au centre de contrôle (le suspect ne voit rien)
                self._send_silent_alert(citizen, watchlist_entry, requesting_user_id)
                self._log(
                    VerificationLog.VerifStatus.REJECTED_WATCHLIST,
                    agent_user_id=requesting_user_id,
                    agent_role=agent_role,
                    citizen=citizen,
                    confidence=confidence,
                    liveness=liveness_score,
                    watchlist_entry=watchlist_entry,
                )
                raise WatchlistHit(
                    alert_level=watchlist_entry.alert_level,
                    reason=watchlist_entry.reason,
                    entry_id=watchlist_entry.pk,
                )

            # ── 5 : Identité confirmée ────────────────────────────────────
            self._log(
                VerificationLog.VerifStatus.VERIFIED,
                agent_user_id=requesting_user_id,
                agent_role=agent_role,
                citizen=citizen,
                confidence=confidence,
                liveness=liveness_score,
            )
            return VerificationResult(
                status=VerificationLog.VerifStatus.VERIFIED,
                citizen=citizen,
                confidence_score=confidence,
                liveness_score=liveness_score,
                watchlist_entry=None,
                message="Identité confirmée.",
            )

        except (FaceNotFound, LivenessDetectionFailed, WatchlistHit):
            raise  # La vue gère ces cas de sécurité
        except Exception as e:
            # Erreur technique (DeepFace OOM, GPU crash, timeout DB…)
            # On NE propage PAS — le service reste en ligne
            logger.error(
                "BIOMETRIC_VERIFY_ERROR",
                extra={'agent_id': requesting_user_id, 'error': str(e)},
                exc_info=True,   # Stack trace dans les logs serveur, pas dans la réponse
            )
            self._log(
                VerificationLog.VerifStatus.ERROR,
                agent_user_id=requesting_user_id,
                agent_role=agent_role,
                citizen=citizen,
            )
            return VerificationResult(
                status=VerificationLog.VerifStatus.ERROR,
                citizen=None,
                confidence_score=None,
                liveness_score=None,
                watchlist_entry=None,
                message="Erreur technique. Réessayez ultérieurement.",
            )

    def register_face(self, citizen: Citizen, image_bytes: bytes) -> CitizenFaceEmbedding:
        """
        Enrôle le visage d'un citoyen : extrait l'embedding et le stocke.
        Appelé lors de la création d'un CitizenFaceEmbedding initial.
        """
        embedding, liveness, quality = self._extract_embedding(image_bytes)
        obj, _ = CitizenFaceEmbedding.objects.update_or_create(
            citizen=citizen,
            defaults={
                'embedding': embedding.tolist(),
                'liveness_score': liveness,
                'quality_score': quality,
                'model_version': self.MODEL_NAME,
            }
        )
        return obj

    # ─────────────────────────────────────────────
    # Méthodes internes
    # ─────────────────────────────────────────────

    def _extract_embedding(
        self, image_bytes: bytes
    ) -> tuple[np.ndarray, Optional[float], Optional[float]]:
        """
        Charge l'image en mémoire, vérifie la liveness, extrait l'embedding ArcFace.
        Retourne (embedding_512d, liveness_score, quality_score).
        """
        from deepface import DeepFace

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        try:
            # anti_spoofing=True est OBLIGATOIRE — jamais optionnel
            result = DeepFace.represent(
                img_path=tmp_path,
                model_name=self.MODEL_NAME,
                detector_backend=self.DETECTOR,
                enforce_detection=True,
                anti_spoofing=True,
            )
        except ValueError as e:
            if 'face' in str(e).lower():
                raise FaceNotFound("Aucun visage détecté dans l'image soumise.") from e
            raise
        finally:
            os.unlink(tmp_path)

        if not result:
            raise FaceNotFound("Aucun visage détecté.")

        face_data = result[0]

        # Vérification liveness explicite
        is_real = face_data.get('is_real', True)
        antispoof_score = face_data.get('antispoof_score', 1.0)

        if not is_real or antispoof_score < self.LIVENESS_THRESHOLD:
            raise LivenessDetectionFailed(
                f"Liveness score {antispoof_score:.2f} < seuil {self.LIVENESS_THRESHOLD}. "
                "Tentative de fraude possible."
            )

        embedding = np.array(face_data['embedding'], dtype=np.float32)
        facial_area = face_data.get('facial_area', {})
        quality_score = face_data.get('face_confidence', None)

        return embedding, antispoof_score, quality_score

    def _search_1n(self, embedding: np.ndarray) -> Optional[tuple[Citizen, float]]:
        """
        Recherche 1:N par similarité cosinus.

        Dev  : scan linéaire en Python sur JSONField (fonctionne sans pgvector).
        Prod : migrer vers pgvector RawSQL('<=>') + index HNSW pour perf 1:N.
        """
        best_citizen = None
        best_score = -1.0

        # Normalise l'embedding requête une seule fois
        norm_q = np.linalg.norm(embedding)
        if norm_q == 0:
            return None
        q = embedding / norm_q

        for row in CitizenFaceEmbedding.objects.select_related('citizen').iterator():
            stored = np.array(row.embedding, dtype=np.float32)
            norm_s = np.linalg.norm(stored)
            if norm_s == 0:
                continue
            score = float(np.dot(q, stored / norm_s))
            if score > best_score:
                best_score = score
                best_citizen = row.citizen

        if best_citizen is None or best_score < self.SIMILARITY_THRESHOLD:
            return None

        return best_citizen, best_score

    def _check_watchlist(self, citizen: Citizen) -> Optional[WatchlistEntry]:
        """Retourne l'entrée watchlist active la plus sévère, ou None."""
        return (
            WatchlistEntry.objects
            .filter(citizen=citizen, is_active=True)
            .filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
            )
            .order_by(
                models.Case(
                    models.When(alert_level='ROUGE', then=0),
                    models.When(alert_level='ORANGE', then=1),
                    models.When(alert_level='JAUNE', then=2),
                    default=3,
                    output_field=models.IntegerField()
                )
            )
            .first()
        )

    def _send_silent_alert(
        self,
        citizen: Citizen,
        entry: WatchlistEntry,
        agent_user_id: int,
    ) -> None:
        """
        Envoie une alerte silencieuse au dashboard de sécurité via Redis pub/sub.
        Le suspect ne voit aucun changement à l'écran.
        Les agents superviseurs reçoivent une notification push immédiate.
        """
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'security_dashboard',
                {
                    'type': 'watchlist_alert',
                    'alert_level': entry.alert_level,
                    'national_id': citizen.national_id,
                    'reason': entry.reason,
                    'issued_by': entry.issued_by,
                    'agent_id': agent_user_id,
                }
            )
        except Exception as e:
            # L'alerte WebSocket ne doit jamais bloquer la vérification
            logger.error("SILENT_ALERT_FAILED", extra={'error': str(e)}, exc_info=True)

    def _log(
        self,
        status: str,
        agent_user_id: int,
        agent_role: str,
        citizen: Optional[Citizen] = None,
        confidence: Optional[float] = None,
        liveness: Optional[float] = None,
        watchlist_entry: Optional[WatchlistEntry] = None,
    ) -> None:
        """Écrit dans VerificationLog. Jamais d'image ou d'embedding ici."""
        VerificationLog.objects.create(
            citizen=citizen,
            agent_user_id=agent_user_id,
            status=status,
            confidence_score=confidence,
            liveness_score=liveness,
            watchlist_hit=watchlist_entry,
            agent_role=agent_role,
        )
        logger.info(
            "BIOMETRIC_VERIFY",
            extra={
                'citizen_id': str(citizen.id) if citizen else None,
                'national_id': citizen.national_id if citizen else None,
                'agent_id': agent_user_id,
                'agent_role': agent_role,
                'result': status,
                'confidence': confidence,
                'liveness': liveness,
                # JAMAIS d'image ou d'embedding ici
            }
        )
