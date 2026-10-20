"""Tests HMAC-SHA256 + ECDSA P-256 — règle sécurité §10.1."""
import json
import pytest
from config.signing import sign_response, verify_ecdsa


PAYLOAD = {'status': 'VERIFIED', 'national_id': 'CG-KN-GBE-999001-T1', 'confidence': 0.9712}


def test_hmac_present():
    signed = sign_response(PAYLOAD)
    assert 'hmac' in signed

def test_hmac_is_hex_64():
    signed = sign_response(PAYLOAD)
    assert len(signed['hmac']) == 64
    assert all(c in '0123456789abcdef' for c in signed['hmac'])

def test_ecdsa_present():
    signed = sign_response(PAYLOAD)
    assert 'ecdsa' in signed, "Les clés ECDSA ne sont pas chargées — vérifie secrets/"

def test_ecdsa_valid():
    signed = sign_response(PAYLOAD)
    clean = {k: v for k, v in signed.items() if k not in ('hmac', 'ecdsa')}
    assert verify_ecdsa(clean, signed['ecdsa'])

def test_ecdsa_rejects_tampered_payload():
    signed = sign_response(PAYLOAD)
    tampered = {k: v for k, v in signed.items() if k not in ('hmac', 'ecdsa')}
    tampered['national_id'] = 'CG-KN-GBE-000000-XX'  # falsifié
    assert not verify_ecdsa(tampered, signed['ecdsa'])

def test_ecdsa_rejects_bad_signature():
    signed = sign_response(PAYLOAD)
    clean = {k: v for k, v in signed.items() if k not in ('hmac', 'ecdsa')}
    assert not verify_ecdsa(clean, 'AAAAAAAAAAAAAAAAAAAAAA==')

def test_hmac_deterministic_for_same_payload():
    s1 = sign_response(PAYLOAD)
    s2 = sign_response(PAYLOAD)
    assert s1['hmac'] == s2['hmac']

def test_original_fields_preserved():
    signed = sign_response(PAYLOAD)
    for k, v in PAYLOAD.items():
        assert signed[k] == v
