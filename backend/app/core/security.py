"""
Security utilities: JWT token creation/verification, password hashing.
All cryptographic operations are centralised here.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    pwd_bytes = plain_password.encode("utf-8")
    if len(pwd_bytes) > 72:
        raise ValueError("Password must not exceed 72 bytes.")
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the plain password matches the stored hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")
        if len(pwd_bytes) > 72:
            return False
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

_TOKEN_TYPE_ACCESS = "access"
_TOKEN_TYPE_REFRESH = "refresh"


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject:      The token subject, typically the user's string ID.
        extra_claims: Additional claims to embed (e.g., role, email).

    Returns:
        Signed JWT string.
    """
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": _TOKEN_TYPE_ACCESS,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Create a long-lived refresh token."""
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": _TOKEN_TYPE_REFRESH,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Raises:
        ValueError: If the token is invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:
        raise ValueError(f"Token validation failed: {exc}") from exc

    if payload.get("type") != _TOKEN_TYPE_ACCESS:
        raise ValueError("Provided token is not an access token.")

    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT refresh token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:
        raise ValueError(f"Refresh token validation failed: {exc}") from exc

    if payload.get("type") != _TOKEN_TYPE_REFRESH:
        raise ValueError("Provided token is not a refresh token.")

    return payload
