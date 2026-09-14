"""The only layer that queries/persists app.db.models.Account directly."""

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db.models import Account, Currency


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, account_id: int) -> Account | None:
        return self._session.get(Account, account_id)

    def get_by_owner_and_currency(self, *, owner: str, currency: Currency) -> Account | None:
        statement = select(Account).where(Account.owner == owner, Account.currency == currency)
        return self._session.exec(statement).first()

    def list_by_owner(self, *, owner: str, page_id: int, page_size: int) -> list[Account]:
        statement = (
            select(Account)
            .where(Account.owner == owner)
            .order_by(sa.text("id"))
            .offset((page_id - 1) * page_size)
            .limit(page_size)
        )
        return list(self._session.exec(statement).all())

    def create(self, *, owner: str, currency: Currency) -> Account:
        account = Account(owner=owner, currency=currency)
        self._session.add(account)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise
        self._session.refresh(account)
        return account

    def apply_balance_delta(self, account: Account, delta: int) -> None:
        """Mutate the balance cache in place. Not committed — the caller
        (TransferService, via TransferRepository.create) controls the
        transaction boundary so the balance updates land atomically with the
        entry/transfer inserts.
        """
        account.balance += delta
        self._session.add(account)
