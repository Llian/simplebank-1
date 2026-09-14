"""Transfer endpoint (requirements §3). Dummy response — no service/repository layer yet."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.schemas.account import AccountResponse
from app.api.schemas.transfer import (
    EntryResponse,
    TransferRequest,
    TransferResponse,
    TransferResult,
)

router = APIRouter(tags=["transfers"])


@router.post("/transfers", response_model=TransferResult)
def create_transfer(payload: TransferRequest) -> TransferResult:
    now = datetime.now(UTC)
    return TransferResult(
        transfer=TransferResponse(
            id=1,
            from_account_id=payload.from_account_id,
            to_account_id=payload.to_account_id,
            amount=payload.amount,
            created_at=now,
        ),
        from_account=AccountResponse(
            id=payload.from_account_id,
            owner="dummy-user",
            balance=0,
            currency=payload.currency,
            created_at=now,
        ),
        to_account=AccountResponse(
            id=payload.to_account_id,
            owner="dummy-user",
            balance=0,
            currency=payload.currency,
            created_at=now,
        ),
        from_entry=EntryResponse(
            id=1, account_id=payload.from_account_id, amount=-payload.amount, created_at=now
        ),
        to_entry=EntryResponse(
            id=2, account_id=payload.to_account_id, amount=payload.amount, created_at=now
        ),
    )
