"""User registration business rules (requirements §4.1-2)."""

from sqlalchemy.exc import IntegrityError

from app.core.errors import DuplicateEmailError, DuplicateUsernameError
from app.core.security import hash_password
from app.db.models import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def _raise_if_duplicate(self, *, username: str, email: str) -> None:
        """Check the fields the DB enforces as unique (see User.__table_args__)."""
        if self._user_repo.get_by_username(username) is not None:
            raise DuplicateUsernameError(f"username '{username}' is already taken") from None
        if self._user_repo.get_by_email(email) is not None:
            raise DuplicateEmailError(f"email '{email}' is already registered") from None

    def register_user(self, *, username: str, password: str, full_name: str, email: str) -> User:
        self._raise_if_duplicate(username=username, email=email)

        hashed_password = hash_password(password)
        try:
            return self._user_repo.create(
                username=username,
                hashed_password=hashed_password,
                full_name=full_name,
                email=email,
            )
        except IntegrityError:
            # Race: another request took the username/email between the check
            # above and this insert. Re-check to raise the specific duplicate
            # error instead of a raw IntegrityError.
            self._raise_if_duplicate(username=username, email=email)
            raise
