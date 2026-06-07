"""Security utilities — JWT token creation/validation and password hashing."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.core.config import settings
from backend.models.user import User, UserResponse

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT token creation
# ---------------------------------------------------------------------------


def create_access_token(user: User, expires_delta: timedelta | None = None, tenant_id: str | None = None) -> str:
    """Create a short-lived JWT access token.

    Args:
        user: The user model.
        expires_delta: Optional custom expiration.
        tenant_id: Override tenant_id in the token (for tenant switching).
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "tenant_id": tenant_id or user.tenant_id,
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user: User, expires_delta: timedelta | None = None) -> str:
    """Create a long-lived JWT refresh token."""
    if expires_delta is None:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "type": "refresh",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# ---------------------------------------------------------------------------
# JWT token validation
# ---------------------------------------------------------------------------


class TokenData:
    """Parsed JWT payload data."""

    def __init__(self, user_id: str, email: str = "", role: str = "", tenant_id: str = "", token_type: str = "access"):
        """Initialise TokenData."""
        self.user_id = user_id
        self.email = email
        self.role = role
        self.tenant_id = tenant_id
        self.token_type = token_type


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT token.

    Raises:
        JWTError: If the token is invalid, expired, or malformed.
    """
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    user_id = payload.get("sub")
    if not user_id:
        raise JWTError("Token missing 'sub' claim")
    return TokenData(
        user_id=user_id,
        email=payload.get("email", ""),
        role=payload.get("role", ""),
        tenant_id=payload.get("tenant_id", ""),
        token_type=payload.get("type", "access"),
    )


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def user_to_response(user: User) -> UserResponse:
    """Convert a User model to a public UserResponse (no password hash)."""
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        tenant_id=user.tenant_id,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )
