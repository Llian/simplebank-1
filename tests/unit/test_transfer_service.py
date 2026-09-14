from datetime import UTC, datetime

import pytest

from app.core.errors import (
    CurrencyMismatchError,
    ForbiddenError,
    InsufficientFundsError,
    NotFoundError,
)
from app.db.models import Account, Currency, Entry, Transfer
from app.services.transfer_service import TransferService


def _make_account(*, id: int, owner: str, currency: Currency, balance: int) -> Account:
    return Account(
        id=id, owner=owner, balance=balance, currency=currency, created_at=datetime.now(UTC)
    )


class FakeAccountRepository:
    def __init__(self, accounts: list[Account]) -> None:
        self.accounts = {a.id: a for a in accounts}

    def get(self, account_id: int) -> Account | None:
        return self.accounts.get(account_id)

    def apply_balance_delta(self, account: Account, delta: int) -> None:
        account.balance += delta


class FakeEntryRepository:
    def __init__(self) -> None:
        self.entries: list[Entry] = []

    def create(self, *, account_id: int, amount: int) -> Entry:
        entry = Entry(
            id=len(self.entries) + 1,
            account_id=account_id,
            amount=amount,
            created_at=datetime.now(UTC),
        )
        self.entries.append(entry)
        return entry


class FakeTransferRepository:
    def __init__(self) -> None:
        self.transfers: list[Transfer] = []

    def create(self, *, from_account_id: int, to_account_id: int, amount: int) -> Transfer:
        transfer = Transfer(
            id=len(self.transfers) + 1,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            created_at=datetime.now(UTC),
        )
        self.transfers.append(transfer)
        return transfer


def _service(accounts: list[Account]) -> TransferService:
    return TransferService(
        FakeAccountRepository(accounts),  # type: ignore[arg-type]
        FakeEntryRepository(),  # type: ignore[arg-type]
        FakeTransferRepository(),  # type: ignore[arg-type]
    )


@pytest.mark.unit
def test_execute_transfer_success_debits_and_credits_balances() -> None:
    accounts = [
        _make_account(id=1, owner="alice", currency=Currency.USD, balance=100),
        _make_account(id=2, owner="bob", currency=Currency.USD, balance=0),
    ]
    service = _service(accounts)

    outcome = service.execute_transfer(
        caller_username="alice",
        from_account_id=1,
        to_account_id=2,
        amount=30,
        currency=Currency.USD,
    )

    assert outcome.from_account.balance == 70
    assert outcome.to_account.balance == 30
    assert outcome.from_entry.amount == -30
    assert outcome.to_entry.amount == 30
    assert outcome.transfer.from_account_id == 1
    assert outcome.transfer.to_account_id == 2
    assert outcome.transfer.amount == 30


@pytest.mark.unit
def test_execute_transfer_from_account_not_found_raises() -> None:
    accounts = [_make_account(id=2, owner="bob", currency=Currency.USD, balance=0)]
    service = _service(accounts)
    with pytest.raises(NotFoundError):
        service.execute_transfer(
            caller_username="alice",
            from_account_id=1,
            to_account_id=2,
            amount=10,
            currency=Currency.USD,
        )


@pytest.mark.unit
def test_execute_transfer_to_account_not_found_raises() -> None:
    accounts = [_make_account(id=1, owner="alice", currency=Currency.USD, balance=100)]
    service = _service(accounts)
    with pytest.raises(NotFoundError):
        service.execute_transfer(
            caller_username="alice",
            from_account_id=1,
            to_account_id=2,
            amount=10,
            currency=Currency.USD,
        )


@pytest.mark.unit
def test_execute_transfer_not_owner_of_from_account_raises_forbidden() -> None:
    accounts = [
        _make_account(id=1, owner="alice", currency=Currency.USD, balance=100),
        _make_account(id=2, owner="bob", currency=Currency.USD, balance=0),
    ]
    service = _service(accounts)
    with pytest.raises(ForbiddenError):
        service.execute_transfer(
            caller_username="bob",
            from_account_id=1,
            to_account_id=2,
            amount=10,
            currency=Currency.USD,
        )


@pytest.mark.unit
def test_execute_transfer_currency_mismatch_between_accounts_raises() -> None:
    accounts = [
        _make_account(id=1, owner="alice", currency=Currency.USD, balance=100),
        _make_account(id=2, owner="bob", currency=Currency.EUR, balance=0),
    ]
    service = _service(accounts)
    with pytest.raises(CurrencyMismatchError):
        service.execute_transfer(
            caller_username="alice",
            from_account_id=1,
            to_account_id=2,
            amount=10,
            currency=Currency.USD,
        )


@pytest.mark.unit
def test_execute_transfer_currency_mismatch_with_request_currency_raises() -> None:
    accounts = [
        _make_account(id=1, owner="alice", currency=Currency.USD, balance=100),
        _make_account(id=2, owner="bob", currency=Currency.USD, balance=0),
    ]
    service = _service(accounts)
    with pytest.raises(CurrencyMismatchError):
        service.execute_transfer(
            caller_username="alice",
            from_account_id=1,
            to_account_id=2,
            amount=10,
            currency=Currency.EUR,
        )


@pytest.mark.unit
def test_execute_transfer_insufficient_funds_raises() -> None:
    accounts = [
        _make_account(id=1, owner="alice", currency=Currency.USD, balance=5),
        _make_account(id=2, owner="bob", currency=Currency.USD, balance=0),
    ]
    service = _service(accounts)
    with pytest.raises(InsufficientFundsError):
        service.execute_transfer(
            caller_username="alice",
            from_account_id=1,
            to_account_id=2,
            amount=10,
            currency=Currency.USD,
        )
