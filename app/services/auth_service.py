"""Login and access-token renewal business rules (requirements §5)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from hmac import compare_digest
from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.errors import InvalidCredentialsError, UnauthorizedError
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from app.db.models import User
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository


@dataclass(frozen=True)
class LoginResult:
    session_id: UUID
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime
    user: User


@dataclass(frozen=True)
class RenewResult:
    access_token: str
    access_token_expires_at: datetime


class AuthService:
    def __init__(
        self, user_repo: UserRepository, session_repo: SessionRepository, settings: Settings
    ) -> None:
        self._user_repo = user_repo
        self._session_repo = session_repo
        self._settings = settings

    def login(
        self, *, username: str, password: str, user_agent: str, client_ip: str
    ) -> LoginResult:
        user = self._user_repo.get_by_username(username)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("incorrect username or password")

        session_id = uuid4()
        refresh_token, refresh_expires_at = create_refresh_token(
            session_id=session_id, settings=self._settings
        )
        self._session_repo.create(
            id=session_id,
            username=user.username,
            refresh_token=refresh_token,
            user_agent=user_agent,
            client_ip=client_ip,
            expires_at=refresh_expires_at,
        )
        access_token, access_expires_at = create_access_token(
            username=user.username, session_id=session_id, settings=self._settings
        )
        return LoginResult(
            session_id=session_id,
            access_token=access_token,
            access_token_expires_at=access_expires_at,
            refresh_token=refresh_token,
            refresh_token_expires_at=refresh_expires_at,
            user=user,
        )

    def renew_access_token(self, *, refresh_token: str) -> RenewResult:
        try:
            session_id = decode_refresh_token(refresh_token, settings=self._settings)
        except TokenError as exc:
            raise UnauthorizedError("invalid or expired refresh token") from exc

        session_row = self._session_repo.get(session_id)
        if session_row is None:
            raise UnauthorizedError("session not found")
        if session_row.is_blocked:
            raise UnauthorizedError("session is blocked")
        expires_at = session_row.expires_at
        if expires_at.tzinfo is None:
            # SQLite drops tzinfo on round-trip; all stored datetimes are UTC
            # (see app.db.models._utcnow / create_refresh_token).
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise UnauthorizedError("session expired")
        if not compare_digest(session_row.refresh_token, refresh_token):
            raise UnauthorizedError("refresh token mismatch")

        access_token, access_expires_at = create_access_token(
            username=session_row.username, session_id=session_row.id, settings=self._settings
        )
        return RenewResult(access_token=access_token, access_token_expires_at=access_expires_at)
