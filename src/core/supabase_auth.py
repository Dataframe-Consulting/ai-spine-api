"""
Supabase token authentication for user management endpoints.
Uses Supabase service key to validate user tokens.
"""
from fastapi import HTTPException, Header
from typing import Optional
import os
import structlog
from supabase import create_client, Client

logger = structlog.get_logger(__name__)

# Read configuration once
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Return a cached Supabase client created with the service key."""
    global _client
    if _client is not None:
        return _client

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        # Falla explícita y clara si faltan variables
        missing = []
        if not SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not SUPABASE_SERVICE_KEY:
            missing.append("SUPABASE_SERVICE_KEY")
        msg = f"Supabase configuration missing: {', '.join(missing)}"
        logger.error("supabase_config_missing", missing=missing)
        raise ValueError(msg)

    _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    logger.info("supabase_client_initialized", url=SUPABASE_URL)
    return _client


def _extract_bearer_token(auth_header: str) -> Optional[str]:
    """
    Extract JWT from Authorization header.
    Accepts variants like 'Bearer <token>' (case-insensitive) and trims spaces.
    """
    if not auth_header:
        return None
    value = auth_header.strip()
    # Case-insensitive 'Bearer ' prefix
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    # Si vino solo el token (no recomendado), lo aceptamos como fallback
    return value if value.count(".") == 2 else None


async def verify_supabase_token(authorization: Optional[str] = Header(None)) -> str:
    """
    Verify Supabase access token and return user_id.
    Intended for protected user-management endpoints.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization format")

    try:
        client = get_supabase_client()
        resp = client.auth.get_user(token)

        # En supabase-py v2, resp.user existe cuando el token es válido
        user = getattr(resp, "user", None)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        # Opcional: exigir email confirmado
        if getattr(user, "confirmed_at", None) is None:
            raise HTTPException(status_code=403, detail="Email not confirmed")

        # Opcional: bloqueo por metadata
        meta = getattr(user, "user_metadata", {}) or {}
        if meta.get("banned"):
            raise HTTPException(status_code=403, detail="User account suspended")

        user_id = user.id
        logger.info("supabase_token_verified", user_id=user_id[:8] + "...")
        return user_id

    except HTTPException:
        # Re-levanta errores ya tipados
        raise
    except Exception as e:
        logger.error("supabase_auth_verification_failed", error=str(e))
        raise HTTPException(status_code=401, detail="Authentication failed")


async def optional_supabase_token(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """
    Soft verification: returns user_id if token is valid, otherwise None.
    """
    if not authorization:
        return None
    try:
        return await verify_supabase_token(authorization)
    except Exception:
        return None


def mask_api_key(api_key: str) -> str:
    """
    Mask API key for logging (first 6 + last 4).
    """
    if not api_key or len(api_key) < 12:
        return "***"
    return f"{api_key[:6]}...{api_key[-4:]}"
