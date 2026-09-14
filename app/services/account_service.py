"""Account business rules (requirements §4.4, §5 ownership)."""

from sqlalchemy.exc import IntegrityError

from app.core.errors import DuplicateAccountError, ForbiddenError, NotFoundError
from app.db.models import Account, Currency
from app.repositories.account_repository import AccountRepository


class AccountService:
    def __init__(self, account_repo: AccountRepository) -> None:
        self._account_repo = account_repo

    def _raise_if_duplicate(self, *, owner: str, currency: Currency) -> None:
        """Check the (owner, currency) uniqueness rule the DB also enforces
        (see Account.__table_args__)."""
        if self._account_repo.get_by_owner_and_currency(owner=owner, currency=currency) is not None:
            raise DuplicateAccountError(
                f"account for owner '{owner}' in currency '{currency}' already exists"
            ) from None

    def create_account(self, *, owner: str, currency: Currency) -> Account:
        self._raise_if_duplicate(owner=owner, currency=currency)

        try:
            return self._account_repo.create(owner=owner, currency=currency)
        except IntegrityError:
            # Race: another request created the (owner, currency) account
            # between the check above and this insert.
            self._raise_if_duplicate(owner=owner, currency=currency)
            raise

    def get_account(self, *, account_id: int, caller_username: str) -> Account:
        account = self._account_repo.get(account_id)
        if account is None:
            raise NotFoundError(f"account {account_id} not found")
        if account.owner != caller_username:
            raise ForbiddenError("you do not own this account")
        return account

    def list_accounts(self, *, owner: str, page_id: int, page_size: int) -> list[Account]:
        return self._account_repo.list_by_owner(owner=owner, page_id=page_id, page_size=page_size)
