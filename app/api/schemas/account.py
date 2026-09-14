from datetime import datetime

from pydantic import BaseModel

from app.db.models import Currency


class AccountCreateRequest(BaseModel):
    currency: Currency


class AccountResponse(BaseModel):
    id: int
    owner: str
    balance: int
    currency: Currency
    created_at: datetime
