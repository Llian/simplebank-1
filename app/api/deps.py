"""DI providers wiring repositories and services into FastAPI routes."""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError
from app.core.security import TokenError, decode_access_token
from app.db.models import User
from app.db.session import get_session
from app.repositories.account_repository import AccountRepository
from app.repositories.entry_repository import EntryRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.transfer_repository import TransferRepository
from app.repositories.user_repository import UserRepository
from app.services.account_service import AccountService
from app.services.auth_service import AuthService
from app.services.transfer_service import TransferService
from app.services.user_service import UserService

_bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(session: Session = Depends(get_session)) -> UserRepository:
    return UserRepository(session)


def get_session_repository(session: Session = Depends(get_session)) -> SessionRepository:
    return SessionRepository(session)


def get_account_repository(session: Session = Depends(get_session)) -> AccountRepository:
    return AccountRepository(session)


def get_entry_repository(session: Session = Depends(get_session)) -> EntryRepository:
    return EntryRepository(session)


def get_transfer_repository(session: Session = Depends(get_session)) -> TransferRepository:
    return TransferRepository(session)


def get_user_service(user_repo: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(user_repo)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(user_repo, session_repo, settings)


def get_account_service(
    account_repo: AccountRepository = Depends(get_account_repository),
) -> AccountService:
    return AccountService(account_repo)


def get_transfer_service(
    account_repo: AccountRepository = Depends(get_account_repository),
    entry_repo: EntryRepository = Depends(get_entry_repository),
    transfer_repo: TransferRepository = Depends(get_transfer_repository),
) -> TransferService:
    return TransferService(account_repo, entry_repo, transfer_repo)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    settings: Settings = Depends(get_settings),
) -> User:
    """Bearer-token auth for /accounts and /transfers (requirements §5).

    Also checks the session row so blocking a session immediately invalidates
    its still-unexpired access token, not just future refreshes.
    """
    if credentials is None:
        raise UnauthorizedError("missing bearer token")

    try:
        payload = decode_access_token(credentials.credentials, settings=settings)
    except TokenError as exc:
        raise UnauthorizedError("invalid or expired access token") from exc

    session_row = session_repo.get(payload.session_id)
    if session_row is None or session_row.is_blocked:
        raise UnauthorizedError("session is invalid")

    user = user_repo.get_by_username(payload.username)
    if user is None:
        raise UnauthorizedError("user not found")
    return user
