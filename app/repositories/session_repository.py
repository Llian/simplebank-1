"""The only layer that queries/persists app.db.models.Session directly."""

from datetime import datetime
from uuid import UUID

from sqlmodel import Session as DbSession

from app.db.models import Session as UserSession


class SessionRepository:
    def __init__(self, session: DbSession) -> None:
        self._session = session

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
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def get(self, session_id: UUID) -> UserSession | None:
        return self._session.get(UserSession, session_id)
