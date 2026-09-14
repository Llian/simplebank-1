"""DI providers wiring repositories and services into FastAPI routes.

get_current_user (bearer-token auth for accounts/transfers) is intentionally
not defined here yet — nothing in the users/tokens surface needs it.
"""

from fastapi import Depends
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.user_service import UserService


def get_user_repository(session: Session = Depends(get_session)) -> UserRepository:
    return UserRepository(session)


def get_session_repository(session: Session = Depends(get_session)) -> SessionRepository:
    return SessionRepository(session)


def get_user_service(user_repo: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(user_repo)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(user_repo, session_repo, settings)
