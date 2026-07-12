"""Unit tests for app/security.py — JWT issuance/decoding and Entra ID token validation."""
import os
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from app.security import create_access_token, decode_access_token, EntraTokenError, validate_entra_id_token


def test_create_and_decode_round_trip():
    token = create_access_token(employee_id=42, role="employee", email="a@x.com")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["role"] == "employee"
    assert payload["email"] == "a@x.com"


def test_decode_rejects_garbage_token():
    assert decode_access_token("not-a-real-jwt") is None


def test_decode_rejects_tampered_token():
    token = create_access_token(employee_id=1, role="employee", email="a@x.com")
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    assert decode_access_token(tampered) is None


def test_shared_admin_flag_round_trips():
    token = create_access_token(employee_id=7, role="hr_admin", email="hr.admin@psiog.com",
                                 acting_display_name="Real Person", is_shared_admin=True)
    payload = decode_access_token(token)
    assert payload["is_shared_admin"] is True
    assert payload["acting_display_name"] == "Real Person"


def test_entra_validation_requires_config():
    """Without ENTRA_TENANT_ID/ENTRA_CLIENT_ID configured, real SSO validation
    must fail loudly rather than silently accepting any token."""
    with pytest.raises(EntraTokenError):
        validate_entra_id_token("whatever.token.here")
