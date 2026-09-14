"""The only layer that queries/persists app.db.models.Transfer directly."""

from sqlmodel import Session

from app.db.models import Transfer


class TransferRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, from_account_id: int, to_account_id: int, amount: int) -> Transfer:
        """Insert the transfer row and commit.

        This is the single commit point for a whole transfer (requirements
        §4 rule 9: debit, credit, both entries, and the transfer row all land
        in one DB transaction): AccountRepository.apply_balance_delta and
        EntryRepository.create stage their changes on this same Session
        without committing, and this call flushes everything together.
        """
        transfer = Transfer(
            from_account_id=from_account_id, to_account_id=to_account_id, amount=amount
        )
        self._session.add(transfer)
        self._session.commit()
        self._session.refresh(transfer)
        return transfer
