from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Account(SQLModel, table=True):
    """Minimal bootstrap subset of the Account model — enough for /internal/test/seed-entry.

    The full Account model (owner FK, currency enum, unique (owner, currency)
    constraint) belongs to the /accounts endpoint work, not this pipeline
    bootstrap.
    """

    id: int | None = Field(default=None, primary_key=True)
    balance: int = 0
    created_at: datetime = Field(default_factory=_utcnow)


class Entry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id")
    amount: int
    created_at: datetime = Field(default_factory=_utcnow)
