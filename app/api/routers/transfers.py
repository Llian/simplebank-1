"""Transfer endpoint (requirements §3, auth required)."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_transfer_service
from app.api.schemas.account import AccountResponse
from app.api.schemas.transfer import (
    EntryResponse,
    TransferRequest,
    TransferResponse,
    TransferResult,
)
from app.db.models import User
from app.services.transfer_service import TransferOutcome, TransferService

router = APIRouter(tags=["transfers"])


def _to_result(outcome: TransferOutcome) -> TransferResult:
    return TransferResult(
        transfer=TransferResponse(
            id=outcome.transfer.id,
            from_account_id=outcome.transfer.from_account_id,
            to_account_id=outcome.transfer.to_account_id,
            amount=outcome.transfer.amount,
            created_at=outcome.transfer.created_at,
        ),
        from_account=AccountResponse(
            id=outcome.from_account.id,
            owner=outcome.from_account.owner,
            balance=outcome.from_account.balance,
            currency=outcome.from_account.currency,
            created_at=outcome.from_account.created_at,
        ),
        to_account=AccountResponse(
            id=outcome.to_account.id,
            owner=outcome.to_account.owner,
            balance=outcome.to_account.balance,
            currency=outcome.to_account.currency,
            created_at=outcome.to_account.created_at,
        ),
        from_entry=EntryResponse(
            id=outcome.from_entry.id,
            account_id=outcome.from_entry.account_id,
            amount=outcome.from_entry.amount,
            created_at=outcome.from_entry.created_at,
        ),
        to_entry=EntryResponse(
            id=outcome.to_entry.id,
            account_id=outcome.to_entry.account_id,
            amount=outcome.to_entry.amount,
            created_at=outcome.to_entry.created_at,
        ),
    )


@router.post("/transfers", response_model=TransferResult)
def create_transfer(
    payload: TransferRequest,
    current_user: User = Depends(get_current_user),
    transfer_service: TransferService = Depends(get_transfer_service),
) -> TransferResult:
    outcome = transfer_service.execute_transfer(
        caller_username=current_user.username,
        from_account_id=payload.from_account_id,
        to_account_id=payload.to_account_id,
        amount=payload.amount,
        currency=payload.currency,
    )
    return _to_result(outcome)
