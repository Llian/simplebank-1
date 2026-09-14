from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.core.errors import InvalidCredentialsError, UnauthorizedError
from app.core.security import create_refresh_token, hash_password
from app.db.models import Session as UserSession
from app.db.models import User
from app.services.auth_service import AuthService

_JWT_SECRET = "test-secret-1234567890-abcdefghij"  # noqa: S105  # nosec B105 -- test fixture
_PASSWORD = "secret123"  # noqa: S105  # nosec B105 -- test fixture
_WRONG_PASSWORD = "wrong-password"  # noqa: S105  # nosec B105 -- test fixture
_GARBAGE_TOKEN = "not-a-jwt"  # noqa: S105  # nosec B105 -- test fixture
_MISMATCHED_TOKEN = "a-different-token"  # noqa: S105  # nosec B105 -- test fixture


def _settings() -> Settings:
    return Settings(jwt_secret_key=_JWT_SECRET)


def _user(username: str = "alice", password: str = _PASSWORD) -> User:
    return User(
        id=1,
        username=username,
        hashed_password=hash_password(password),
        full_name="Alice A",
        email="alice@example.com",
        password_changed_at=datetime.fromtimestamp(0, tz=UTC),
        created_at=datetime.now(UTC),
    )


class FakeUserRepository:
    def __init__(self, user: User | None) -> None:
        self._user = user

    def get_by_username(self, username: str) -> User | None:
        if self._user is not None and self._user.username.lower() == username.lower():
            return self._user
        return None

    def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError


class FakeSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, UserSession] = {}

    def create(
        self,
        *,
        id: UUID,
        username: str,
        refresh_token: str,
        user_agent: str,
        client_ip: str,
        expires_at: datetime,
    ) -> UserSession:
        row = UserSession(
            id=id,
            username=username,
            refresh_token=refresh_token,
            user_agent=user_agent,
            client_ip=client_ip,
            expires_at=expires_at,
        )
        self.sessions[id] = row
        return row

    def get(self, session_id: UUID) -> UserSession | None:
        return self.sessions.get(session_id)


def _auth_service(
    user: User | None, session_repo: FakeSessionRepository, settings: Settings
) -> AuthService:
    return AuthService(
        FakeUserRepository(user),  # type: ignore[arg-type]
        session_repo,  # type: ignore[arg-type]
        settings,
    )


@pytest.mark.unit
def test_login_success_creates_session_and_returns_tokens() -> None:
    session_repo = FakeSessionRepository()
    service = _auth_service(_user(), session_repo, _settings())

    result = service.login(
        username="alice", password=_PASSWORD, user_agent="pytest", client_ip="127.0.0.1"
    )

    assert result.user.username == "alice"
    assert result.session_id in session_repo.sessions
    assert session_repo.sessions[result.session_id].refresh_token == result.refresh_token


@pytest.mark.unit
def test_login_unknown_username_raises_invalid_credentials() -> None:
    service = _auth_service(None, FakeSessionRepository(), _settings())
    with pytest.raises(InvalidCredentialsError):
        service.login(username="nobody", password=_PASSWORD, user_agent="", client_ip="")


@pytest.mark.unit
def test_login_wrong_password_raises_invalid_credentials() -> None:
    service = _auth_service(_user(), FakeSessionRepository(), _settings())
    with pytest.raises(InvalidCredentialsError):
        service.login(username="alice", password=_WRONG_PASSWORD, user_agent="", client_ip="")


def _login_and_get_session(
    session_repo: FakeSessionRepository, settings: Settings
) -> tuple[AuthService, str, UUID]:
    service = _auth_service(_user(), session_repo, settings)
    result = service.login(username="alice", password=_PASSWORD, user_agent="", client_ip="")
    return service, result.refresh_token, result.session_id


@pytest.mark.unit
def test_renew_access_token_success() -> None:
    settings = _settings()
    service, refresh_token, _ = _login_and_get_session(FakeSessionRepository(), settings)
    result = service.renew_access_token(refresh_token=refresh_token)
    assert result.access_token


@pytest.mark.unit
def test_renew_access_token_malformed_token_raises_unauthorized() -> None:
    service = _auth_service(None, FakeSessionRepository(), _settings())
    with pytest.raises(UnauthorizedError):
        service.renew_access_token(refresh_token=_GARBAGE_TOKEN)


@pytest.mark.unit
def test_renew_access_token_session_not_found_raises_unauthorized() -> None:
    settings = _settings()
    service = _auth_service(None, FakeSessionRepository(), settings)
    token, _ = create_refresh_token(session_id=uuid4(), settings=settings)
    with pytest.raises(UnauthorizedError):
        service.renew_access_token(refresh_token=token)


@pytest.mark.unit
def test_renew_access_token_blocked_session_raises_unauthorized() -> None:
    settings = _settings()
    session_repo = FakeSessionRepository()
    service, refresh_token, session_id = _login_and_get_session(session_repo, settings)
    session_repo.sessions[session_id].is_blocked = True
    with pytest.raises(UnauthorizedError):
        service.renew_access_token(refresh_token=refresh_token)


@pytest.mark.unit
def test_renew_access_token_expired_session_row_raises_unauthorized() -> None:
    settings = _settings()
    session_repo = FakeSessionRepository()
    service, refresh_token, session_id = _login_and_get_session(session_repo, settings)
    session_repo.sessions[session_id].expires_at = datetime.now(UTC) - timedelta(hours=1)
    with pytest.raises(UnauthorizedError):
        service.renew_access_token(refresh_token=refresh_token)


@pytest.mark.unit
def test_renew_access_token_mismatched_stored_token_raises_unauthorized() -> None:
    settings = _settings()
    session_repo = FakeSessionRepository()
    service, refresh_token, session_id = _login_and_get_session(session_repo, settings)
    session_repo.sessions[session_id].refresh_token = _MISMATCHED_TOKEN
    with pytest.raises(UnauthorizedError):
        service.renew_access_token(refresh_token=refresh_token)
