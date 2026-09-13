"""Data model per requirements/simplebank-requirements.md §2.

Account balance is a maintained cache; Entry rows are the source of truth —
balance always equals the sum of that account's entries. No API endpoints or
business logic (auth, transfer execution, etc.) belong here — see
docs/test-pipeline-design.md's scope boundary.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import CheckConstraint, Field, Index, Relationship, SQLModel, UniqueConstraint


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _epoch_zero() -> datetime:
    return datetime.fromtimestamp(0, tz=UTC)


class Currency(StrEnum):
    USD = "USD"
    EUR = "EUR"
    CAD = "CAD"


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        # Case-insensitive uniqueness (business rule 1) enforced at the DB
        # level via a functional index, not left to application-layer checks
        # alone — those are vulnerable to a TOCTOU race between concurrent
        # registrations.
        Index("ux_users_username_lower", sa.text("lower(username)"), unique=True),
    )

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, min_length=3, max_length=32)
    hashed_password: str
    full_name: str
    email: str = Field(unique=True, index=True)
    password_changed_at: datetime = Field(default_factory=_epoch_zero)
    created_at: datetime = Field(default_factory=_utcnow)

    accounts: list["Account"] = Relationship(back_populates="owner_user")
    sessions: list["Session"] = Relationship(back_populates="user")


class Account(SQLModel, table=True):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("owner", "currency", name="uq_account_owner_currency"),
        # Field(ge=0) alone is Pydantic-only: it doesn't produce a DB
        # constraint and isn't re-checked on attribute mutation (e.g.
        # `account.balance += amount` on an already-loaded row), so it can't
        # stop a negative balance from being committed on its own.
        CheckConstraint("balance >= 0", name="ck_account_balance_nonnegative"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner: str = Field(foreign_key="users.username", index=True)
    balance: int = Field(default=0, ge=0)
    currency: Currency
    created_at: datetime = Field(default_factory=_utcnow)

    owner_user: User | None = Relationship(back_populates="accounts")
    entries: list["Entry"] = Relationship(back_populates="account")


class Entry(SQLModel, table=True):
    __tablename__ = "entries"

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    amount: int
    created_at: datetime = Field(default_factory=_utcnow)

    account: Account | None = Relationship(back_populates="entries")


class Transfer(SQLModel, table=True):
    __tablename__ = "transfers"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_transfer_amount_positive"),)

    id: int | None = Field(default=None, primary_key=True)
    from_account_id: int = Field(foreign_key="accounts.id", index=True)
    to_account_id: int = Field(foreign_key="accounts.id", index=True)
    amount: int = Field(gt=0)
    created_at: datetime = Field(default_factory=_utcnow)

    from_account: Account | None = Relationship(
        sa_relationship_kwargs={"foreign_keys": "Transfer.from_account_id"}
    )
    to_account: Account | None = Relationship(
        sa_relationship_kwargs={"foreign_keys": "Transfer.to_account_id"}
    )


class Session(SQLModel, table=True):
    """Refresh-token tracking (requirements §2, §5).

    Named to match the requirements doc; shadows sqlmodel.Session (the DB
    session object) when both are imported together — alias one side, e.g.
    `from app.db.models import Session as UserSession`.
    """

    __tablename__ = "sessions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(foreign_key="users.username", index=True)
    refresh_token: str
    user_agent: str
    client_ip: str
    is_blocked: bool = Field(default=False)
    expires_at: datetime
    created_at: datetime = Field(default_factory=_utcnow)

    user: User | None = Relationship(back_populates="sessions")
