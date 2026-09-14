"""Password hashing and JWT access/refresh token helpers (requirements §5).

Access tokens carry `username` + `session_id`, 15 min TTL. Refresh tokens
carry only `session_id`, 24h TTL — the session row (looked up by primary key)
is the source of truth for blocked/expired/mismatch checks, done by
app.services.auth_service. Both token kinds carry a `type` claim so an access
token can never be replayed where a refresh token is expected, or vice versa.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from app.core.config import Settings

ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised for any missing/malformed/invalid-signature/expired/wrong-type token."""


@dataclass(frozen=True)
class AccessTokenPayload:
    username: str
    session_id: UUID


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    *, username: str, session_id: UUID, settings: Settings
) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_ttl_minutes)
    token = jwt.encode(
        {
            "username": username,
            "session_id": str(session_id),
            "type": "access",
            "exp": expires_at,
        },
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )
    return token, expires_at


def decode_access_token(token: str, *, settings: Settings) -> AccessTokenPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError("invalid or expired access token") from exc
    if payload.get("type") != "access":
        raise TokenError("wrong token type")
    return AccessTokenPayload(username=payload["username"], session_id=UUID(payload["session_id"]))


def create_refresh_token(*, session_id: UUID, settings: Settings) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(hours=settings.refresh_token_ttl_hours)
    token = jwt.encode(
        {"session_id": str(session_id), "type": "refresh", "exp": expires_at},
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )
    return token, expires_at


def decode_refresh_token(token: str, *, settings: Settings) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError("invalid or expired refresh token") from exc
    if payload.get("type") != "refresh":
        raise TokenError("wrong token type")
    return UUID(payload["session_id"])
