"""The only layer that queries/persists app.db.models.Entry directly."""

from sqlmodel import Session

from app.db.models import Entry


class EntryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, account_id: int, amount: int) -> Entry:
        """Stage a new entry. Not committed — see AccountRepository.apply_balance_delta;
        this participates in the same transfer transaction, committed by
        TransferRepository.create.
        """
        entry = Entry(account_id=account_id, amount=amount)
        self._session.add(entry)
        return entry
