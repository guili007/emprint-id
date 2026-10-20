"""
Signatures cryptographiques des réponses API EmPrint-iD.

Deux couches complémentaires :
  - HMAC-SHA256  : intégrité en transit (symétrique, rapide)
  - ECDSA P-256  : preuve vérifiable par tiers (asymétrique, auditeurs / tribunaux)

Les clés sont chargées une seule fois au démarrage (module-level).
Si les fichiers PEM sont absents (env de CI / test), on dégrade gracieusement.
"""
import base64
import hashlib
import hmac
import json
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger('emprint.signing')

# ── Chargement des clés ECDSA au démarrage ────────────────────────────────────

_private_key = None
_public_key = None


def _load_keys():
    global _private_key, _public_key
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec  # noqa: F401

        priv_path = Path(settings.ECDSA_PRIVATE_KEY_PATH)
        pub_path  = Path(settings.ECDSA_PUBLIC_KEY_PATH)

        if priv_path.exists() and pub_path.exists():
            _private_key = serialization.load_pem_private_key(
                priv_path.read_bytes(), password=None
            )
            _public_key = serialization.load_pem_public_key(pub_path.read_bytes())
    except Exception as e:
        logger.warning("ECDSA_KEYS_UNAVAILABLE — dégradé HMAC uniquement: %s", e)


_load_keys()


# ── Fonctions publiques ───────────────────────────────────────────────────────

def sign_response(payload: dict) -> dict:
    """
    Ajoute HMAC-SHA256 + signature ECDSA P-256 au payload.

    Le champ `ecdsa` est absent si les clés ne sont pas chargées (CI / test).
    """
    body = json.dumps(payload, sort_keys=True, default=str)

    # HMAC — symétrique, vérifiable par le backend uniquement
    mac = hmac.new(
        settings.HMAC_SECRET_KEY.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()

    signed = {**payload, 'hmac': mac}

    # ECDSA — asymétrique, vérifiable par n'importe qui avec la clé publique
    if _private_key is not None:
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import ec

            sig_bytes = _private_key.sign(body.encode(), ec.ECDSA(hashes.SHA256()))
            signed['ecdsa'] = base64.b64encode(sig_bytes).decode()
        except Exception as e:
            logger.error("ECDSA_SIGN_FAILED: %s", e, exc_info=True)

    return signed


def verify_ecdsa(payload_without_sigs: dict, ecdsa_b64: str) -> bool:
    """Vérifie une signature ECDSA reçue. Utile pour les auditeurs / tests."""
    if _public_key is None:
        return False
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.exceptions import InvalidSignature

        body = json.dumps(payload_without_sigs, sort_keys=True, default=str)
        sig = base64.b64decode(ecdsa_b64)
        _public_key.verify(sig, body.encode(), ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False
