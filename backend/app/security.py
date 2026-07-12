"""
Authentication: real Microsoft Entra ID SSO, with a dev-only mock fallback.

Two identity paths land here:

1. Individual employees/managers - a real person signs in with their own
   Microsoft account. Their Entra ID OID/email is matched 1:1 against their
   own `employees` row (personal data lives there: leave, payslips,
   attendance, profile).

2. Shared HR Admin / IT Admin accounts - these are FUNCTIONAL roles, not
   people. Multiple real staff can be members of an Entra ID security group
   (ENTRA_HR_ADMIN_GROUP_ID / ENTRA_IT_ADMIN_GROUP_ID). Whoever signs in and
   is a member of that group is authenticated INTO the shared "HR Admin" /
   "IT Admin" employees row (which holds zero personal data - see
   employees.is_shared_admin) rather than needing to be individually
   provisioned as "the" admin. Every such login is written to
   admin_account_access_log with the real person's identity, so actions are
   still attributable even though the account itself isn't a person.

USE_MOCK_SSO=true (the default so this zip runs without an Azure tenant)
skips real Microsoft token validation and instead trusts a dev-only email
picker - see routers/auth.py `dev_mock_login`. Set USE_MOCK_SSO=false and
fill in ENTRA_TENANT_ID / ENTRA_CLIENT_ID to validate real tokens minted by
Microsoft Entra ID via MSAL.js on the frontend (routers/auth.py `sso_login`).
"""
import time
from datetime import datetime, timedelta, timezone

import httpx
from jose import jwt, JWTError

from app.config import settings

# -- App-issued session JWT (unchanged regardless of identity provider) -----

def create_access_token(employee_id: int, role: str, email: str,
                         acting_display_name: str | None = None,
                         is_shared_admin: bool = False) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRES_MINUTES)
    payload = {
        "sub": str(employee_id),
        "role": role,
        "email": email,
        "acting_display_name": acting_display_name,
        "is_shared_admin": is_shared_admin,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# -- Real Microsoft Entra ID token validation --------------------------------

_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}


def _entra_jwks_uri() -> str:
    return f"https://login.microsoftonline.com/{settings.ENTRA_TENANT_ID}/discovery/v2.0/keys"


def _entra_issuer() -> str:
    return f"https://login.microsoftonline.com/{settings.ENTRA_TENANT_ID}/v2.0"


def _get_jwks() -> dict:
    now = time.time()
    if _jwks_cache["keys"] is None or (now - _jwks_cache["fetched_at"]) > settings.ENTRA_JWKS_CACHE_SECONDS:
        resp = httpx.get(_entra_jwks_uri(), timeout=10.0)
        resp.raise_for_status()
        _jwks_cache["keys"] = resp.json()
        _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]


class EntraTokenError(Exception):
    pass


def validate_entra_id_token(id_token: str) -> dict:
    """
    Validates a Microsoft Entra ID id_token (as returned to the frontend by
    MSAL.js after sign-in) against Microsoft's public JWKS for our tenant,
    and returns the decoded claims.

    Requires ENTRA_TENANT_ID / ENTRA_CLIENT_ID to be configured. Raises
    EntraTokenError on any validation failure (bad signature, wrong
    issuer/audience, expired token).
    """
    if not settings.ENTRA_TENANT_ID or not settings.ENTRA_CLIENT_ID:
        raise EntraTokenError(
            "ENTRA_TENANT_ID / ENTRA_CLIENT_ID are not configured on the backend. "
            "Register an app in your Azure tenant and set these in backend/.env."
        )
    try:
        jwks = _get_jwks()
        unverified_header = jwt.get_unverified_header(id_token)
        key = next((k for k in jwks["keys"] if k["kid"] == unverified_header.get("kid")), None)
        if key is None:
            raise EntraTokenError("Signing key not found in Entra ID JWKS (token may be forged or JWKS rotated).")
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=settings.ENTRA_CLIENT_ID,
            issuer=_entra_issuer(),
        )
        return claims
    except JWTError as e:
        raise EntraTokenError(f"Entra ID token failed validation: {e}")
    except httpx.HTTPError as e:
        raise EntraTokenError(f"Could not reach Microsoft's JWKS endpoint: {e}")


def extract_identity(claims: dict) -> dict:
    """
    Normalizes the fields we need off an Entra ID token: real person's OID,
    email, display name, and group memberships (used to resolve shared
    HR Admin / IT Admin access - see module docstring).

    NOTE: Entra ID only embeds a `groups` claim directly on the token for a
    limited number of groups; for tenants with many groups it instead sets
    `_claim_names` / `hasgroups`, requiring a Microsoft Graph
    `/me/memberOf` call to enumerate group membership. Where that applies,
    replace the `claims.get("groups", [])` line below with a Graph API
    lookup using the access token from the same MSAL.js sign-in.
    """
    return {
        "oid": claims.get("oid") or claims.get("sub"),
        "email": (claims.get("preferred_username") or claims.get("email") or "").lower(),
        "display_name": claims.get("name"),
        "groups": claims.get("groups", []),
    }
