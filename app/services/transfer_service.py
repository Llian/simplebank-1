"""Transfer execution business rules (requirements §4 rules 5-9)."""

from dataclasses import dataclass

from app.core.errors import (
    CurrencyMismatchError,
    ForbiddenError,
    InsufficientFundsError,
    NotFoundError,
)
from app.db.models import Account, Currency, Entry, Transfer
from app.repositories.account_repository import AccountRepository
from app.repositories.entry_repository import EntryRepository
from app.repositories.transfer_repository import TransferRepository


@dataclass(frozen=True)
class TransferOutcome:
    transfer: Transfer
    from_account: Account
    to_account: Account
    from_entry: Entry
    to_entry: Entry


def _require_id(account: Account) -> int:
    """Accounts loaded from the repository are always persisted, so id is
    always set; the Optional in the model type is only for the pre-insert
    construction case."""
    if account.id is None:
        raise RuntimeError("account loaded from the repository has no id")
    return account.id


class TransferService:
    def __init__(
        self,
        account_repo: AccountRepository,
        entry_repo: EntryRepository,
        transfer_repo: TransferRepository,
    ) -> None:
        self._account_repo = account_repo
        self._entry_repo = entry_repo
        self._transfer_repo = transfer_repo

    def _get_account_or_404(self, account_id: int) -> Account:
        account = self._account_repo.get(account_id)
        if account is None:
            raise NotFoundError(f"account {account_id} not found")
        return account

    def execute_transfer(
        self,
        *,
        caller_username: str,
        from_account_id: int,
        to_account_id: int,
        amount: int,
        currency: Currency,
    ) -> TransferOutcome:
        from_account = self._get_account_or_404(from_account_id)
        to_account = self._get_account_or_404(to_account_id)

        if from_account.owner != caller_username:
            raise ForbiddenError("you do not own the source account")

        if from_account.currency != currency or to_account.currency != currency:
            raise CurrencyMismatchError(
                "from_account, to_account, and request currencies must all match"
            )

        if from_account.balance < amount:
            raise InsufficientFundsError("source account balance is too low for this transfer")

        from_account_pk = _require_id(from_account)
        to_account_pk = _require_id(to_account)

        self._account_repo.apply_balance_delta(from_account, -amount)
        self._account_repo.apply_balance_delta(to_account, amount)
        from_entry = self._entry_repo.create(account_id=from_account_pk, amount=-amount)
        to_entry = self._entry_repo.create(account_id=to_account_pk, amount=amount)
        transfer = self._transfer_repo.create(
            from_account_id=from_account_pk, to_account_id=to_account_pk, amount=amount
        )

        return TransferOutcome(
            transfer=transfer,
            from_account=from_account,
            to_account=to_account,
            from_entry=from_entry,
            to_entry=to_entry,
        )
