"""The only layer that queries/persists app.db.models.User directly."""

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(func.lower(User.username) == username.lower())
        return self._session.exec(statement).first()

    def get_by_email(self, email: str) -> User | None:
        return self._session.exec(select(User).where(User.email == email)).first()

    def create(self, *, username: str, hashed_password: str, full_name: str, email: str) -> User:
        user = User(
            username=username, hashed_password=hashed_password, full_name=full_name, email=email
        )
        self._session.add(user)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise
        self._session.refresh(user)
        return user
