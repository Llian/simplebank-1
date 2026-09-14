"""Account endpoints (requirements §3, auth required)."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_account_service, get_current_user
from app.api.schemas.account import AccountCreateRequest, AccountResponse
from app.db.models import Account, User
from app.services.account_service import AccountService

router = APIRouter(tags=["accounts"])


def _to_response(account: Account) -> AccountResponse:
    return AccountResponse(
        id=account.id,
        owner=account.owner,
        balance=account.balance,
        currency=account.currency,
        created_at=account.created_at,
    )


@router.post("/accounts", response_model=AccountResponse, status_code=201)
def create_account(
    payload: AccountCreateRequest,
    current_user: User = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    account = account_service.create_account(owner=current_user.username, currency=payload.currency)
    return _to_response(account)


@router.get("/accounts/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    account = account_service.get_account(
        account_id=account_id, caller_username=current_user.username
    )
    return _to_response(account)


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(
    page_id: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service),
) -> list[AccountResponse]:
    accounts = account_service.list_accounts(
        owner=current_user.username, page_id=page_id, page_size=page_size
    )
    return [_to_response(account) for account in accounts]
