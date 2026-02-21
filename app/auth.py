"""
Google OAuth and session handling for admin-only access.
Session is a signed httpOnly cookie (SameSite=None, Secure for cross-origin).
"""
from __future__ import annotations

import logging
import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request, Response
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from itsdangerous import BadSignature, URLSafeTimedSerializer

logger = logging.getLogger(__name__)

# Cookie name and settings for cross-origin (GitHub Pages -> Azure backend)
SESSION_COOKIE_NAME = "hatch_session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 days
# Secret for signing session; must be set in production
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32)

_serializer: URLSafeTimedSerializer | None = None


def _get_serializer() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        _serializer = URLSafeTimedSerializer(
            SESSION_SECRET,
            salt="hatch-admin-session",
            signer_kwargs={"key_derivation": "hmac", "digest_method": "sha256"},
        )
    return _serializer


def get_allowlist_emails() -> set[str]:
    """Return set of emails allowed to access admin (from ADMIN_ALLOWLIST_EMAILS)."""
    raw = os.environ.get("ADMIN_ALLOWLIST_EMAILS", "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def create_session_cookie(email: str) -> str:
    """Serialize session payload and return signed cookie value."""
    payload = {"email": email.lower()}
    return _get_serializer().dumps(payload)


def create_bearer_token(email: str) -> str:
    """Create a signed bearer token for cross-site auth (mobile/cross-origin). Same format as cookie."""
    return create_session_cookie(email)


def load_bearer_token(token: str) -> dict | None:
    """Verify bearer token and return payload; None if invalid."""
    return load_session(token)


def load_session(cookie_value: str) -> dict | None:
    """Verify and deserialize session cookie; return payload or None if invalid/expired."""
    if not cookie_value:
        return None
    try:
        payload = _get_serializer().loads(cookie_value, max_age=SESSION_MAX_AGE_SECONDS)
        return payload
    except BadSignature:
        return None
    except Exception:
        return None


def get_session_email(request: Request) -> str:
    """
    Read session from cookie or Authorization Bearer token. Cookie works for same-site;
    Bearer token works for cross-origin/mobile (avoids third-party cookie blocking).
    Raises HTTPException 401 if not authenticated or not allowlisted.
    """
    payload = None
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_value:
        payload = load_session(cookie_value)
    if not payload:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            if token:
                payload = load_bearer_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Not authenticated")
    email = (payload.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Invalid session")
    allowlist = get_allowlist_emails()
    if not allowlist:
        logger.warning("ADMIN_ALLOWLIST_EMAILS is not set; no one can log in as admin")
        raise HTTPException(status_code=401, detail="Admin access not configured")
    if email not in allowlist:
        raise HTTPException(status_code=403, detail="Not allowed")
    return email


def set_session_response(response: Response, email: str) -> None:
    """Set the session cookie on the response (httpOnly, SameSite=None, Secure)."""
    value = create_session_cookie(email)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        value,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="none",
        secure=True,
    )


def clear_session_response(response: Response) -> None:
    """Clear the session cookie."""
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        httponly=True,
        samesite="none",
        secure=True,
    )


# Google OAuth
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/photoslibrary.readonly",
]


def get_google_client_config() -> tuple[str, str]:
    """Return (client_id, client_secret); raises ValueError if unset."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set")
    return client_id, client_secret


def build_google_auth_url(redirect_uri: str, state: str | None = None) -> str:
    """Build the Google OAuth authorization URL."""
    client_id, _ = get_google_client_config()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    """Exchange authorization code for tokens. Returns dict with id_token, access_token, refresh_token (if granted)."""
    client_id, client_secret = get_google_client_config()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    resp.raise_for_status()
    return resp.json()


def verify_google_id_token(id_token_str: str, client_id: str) -> dict:
    """Verify Google ID token and return decoded claims (e.g. email)."""
    return id_token.verify_oauth2_token(
        id_token_str,
        google_requests.Request(),
        client_id,
    )


async def refresh_access_token(refresh_token: str) -> str:
    """Exchange refresh_token for a new access_token. Raises on error."""
    client_id, client_secret = get_google_client_config()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    resp.raise_for_status()
    data = resp.json()
    access = data.get("access_token")
    if not access:
        raise ValueError("No access_token in refresh response")
    return access
