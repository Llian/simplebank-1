from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import DuplicateEmailError, DuplicateUsernameError
from app.db.models import User
from app.services.user_service import UserService

_PASSWORD = "secret123"  # noqa: S105  # nosec B105 -- test fixture
_OTHER_PASSWORD = "other1234"  # noqa: S105  # nosec B105 -- test fixture
_FAKE_HASHED_PASSWORD = "not-a-real-hash"  # noqa: S105  # nosec B105 -- test fixture


def _make_user(*, id: int, username: str, email: str) -> User:
    return User(
        id=id,
        username=username,
        hashed_password=_FAKE_HASHED_PASSWORD,
        full_name="Full Name",
        email=email,
        password_changed_at=datetime.fromtimestamp(0, tz=UTC),
        created_at=datetime.now(UTC),
    )


class FakeUserRepository:
    """Fake with a pre-populated `users` table and a create() that can be
    made to raise IntegrityError, to simulate a duplicate-check race: the
    pre-check (first get_by_username/get_by_email call) misses, then create()
    fails because a concurrent request won the race, and the post-check
    (second call) now sees the row.
    """

    def __init__(self, existing: list[User] | None = None) -> None:
        self.users: list[User] = list(existing or [])
        self.raise_integrity_error_on_create = False
        self.get_by_username_call_count = 0
        self.get_by_email_call_count = 0
        self.miss_first_get_by_username_call = False
        self.miss_first_get_by_email_call = False

    def get_by_username(self, username: str) -> User | None:
        self.get_by_username_call_count += 1
        if self.miss_first_get_by_username_call and self.get_by_username_call_count == 1:
            return None
        return next((u for u in self.users if u.username.lower() == username.lower()), None)

    def get_by_email(self, email: str) -> User | None:
        self.get_by_email_call_count += 1
        if self.miss_first_get_by_email_call and self.get_by_email_call_count == 1:
            return None
        return next((u for u in self.users if u.email == email), None)

    def create(self, *, username: str, hashed_password: str, full_name: str, email: str) -> User:
        if self.raise_integrity_error_on_create:
            raise IntegrityError("insert", {}, Exception("unique constraint"))
        user = _make_user(id=len(self.users) + 1, username=username, email=email)
        self.users.append(user)
        return user


@pytest.mark.unit
def test_register_user_success() -> None:
    service = UserService(FakeUserRepository())  # type: ignore[arg-type]
    user = service.register_user(
        username="alice", password=_PASSWORD, full_name="Alice A", email="alice@example.com"
    )
    assert user.username == "alice"


@pytest.mark.unit
def test_register_user_stores_hashed_not_plaintext_password() -> None:
    repo = FakeUserRepository()
    service = UserService(repo)  # type: ignore[arg-type]
    service.register_user(
        username="alice", password=_PASSWORD, full_name="Alice A", email="alice@example.com"
    )
    assert repo.users[0].hashed_password != _PASSWORD


@pytest.mark.unit
def test_register_user_duplicate_username_raises() -> None:
    repo = FakeUserRepository(existing=[_make_user(id=1, username="alice", email="a@example.com")])
    service = UserService(repo)  # type: ignore[arg-type]
    with pytest.raises(DuplicateUsernameError):
        service.register_user(
            username="alice",
            password=_OTHER_PASSWORD,
            full_name="Alice B",
            email="other@example.com",
        )


@pytest.mark.unit
def test_register_user_duplicate_email_raises() -> None:
    repo = FakeUserRepository(existing=[_make_user(id=1, username="alice", email="a@example.com")])
    service = UserService(repo)  # type: ignore[arg-type]
    with pytest.raises(DuplicateEmailError):
        service.register_user(
            username="alice2", password=_OTHER_PASSWORD, full_name="Alice B", email="a@example.com"
        )


@pytest.mark.unit
def test_register_user_integrity_error_race_resolves_to_duplicate_username() -> None:
    repo = FakeUserRepository(existing=[_make_user(id=1, username="alice", email="a@example.com")])
    repo.raise_integrity_error_on_create = True
    repo.miss_first_get_by_username_call = True
    service = UserService(repo)  # type: ignore[arg-type]

    with pytest.raises(DuplicateUsernameError):
        service.register_user(
            username="alice", password=_PASSWORD, full_name="Alice B", email="new@example.com"
        )


@pytest.mark.unit
def test_register_user_integrity_error_race_resolves_to_duplicate_email() -> None:
    repo = FakeUserRepository(existing=[_make_user(id=1, username="alice", email="a@example.com")])
    repo.raise_integrity_error_on_create = True
    repo.miss_first_get_by_email_call = True
    service = UserService(repo)  # type: ignore[arg-type]

    with pytest.raises(DuplicateEmailError):
        service.register_user(
            username="new_user", password=_PASSWORD, full_name="New User", email="a@example.com"
        )
