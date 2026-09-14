"""Account endpoints (requirements §3). Dummy responses — no service/repository layer yet."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.schemas.account import AccountCreateRequest, AccountResponse
from app.db.models import Currency

router = APIRouter(tags=["accounts"])


def _dummy_account(account_id: int, currency: Currency = Currency.USD) -> AccountResponse:
    return AccountResponse(
        id=account_id,
        owner="dummy-user",
        balance=0,
        currency=currency,
        created_at=datetime.now(UTC),
    )


@router.post("/accounts", response_model=AccountResponse, status_code=201)
def create_account(payload: AccountCreateRequest) -> AccountResponse:
    return _dummy_account(account_id=1, currency=payload.currency)


@router.get("/accounts/{account_id}", response_model=AccountResponse)
def get_account(account_id: int) -> AccountResponse:
    return _dummy_account(account_id=account_id)


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(page_id: int = 1, page_size: int = 10) -> list[AccountResponse]:
    return [_dummy_account(account_id=1)]
