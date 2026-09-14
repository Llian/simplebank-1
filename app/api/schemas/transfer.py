from datetime import datetime

from pydantic import BaseModel

from app.api.schemas.account import AccountResponse
from app.db.models import Currency


class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: int
    currency: Currency


class EntryResponse(BaseModel):
    id: int
    account_id: int
    amount: int
    created_at: datetime


class TransferResponse(BaseModel):
    id: int
    from_account_id: int
    to_account_id: int
    amount: int
    created_at: datetime


class TransferResult(BaseModel):
    transfer: TransferResponse
    from_account: AccountResponse
    to_account: AccountResponse
    from_entry: EntryResponse
    to_entry: EntryResponse
