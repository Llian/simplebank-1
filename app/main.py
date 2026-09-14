from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.api.routers.accounts import router as accounts_router
from app.api.routers.tokens import router as tokens_router
from app.api.routers.transfers import router as transfers_router
from app.api.routers.users import router as users_router
from app.core.config import get_settings
from app.db.models import Account, Entry
from app.db.session import create_db_and_tables, get_session

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.environment != "production":
        create_db_and_tables()
    yield


app = FastAPI(title="Simple Bank", lifespan=lifespan)

app.include_router(users_router)
app.include_router(tokens_router)
app.include_router(accounts_router)
app.include_router(transfers_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


class SeedEntryRequest(BaseModel):
    account_id: int
    amount: int


class SeedEntryResponse(BaseModel):
    account_id: int
    balance: int


@app.post("/internal/test/seed-entry", response_model=SeedEntryResponse, status_code=201)
def seed_entry(
    payload: SeedEntryRequest, session: Session = Depends(get_session)
) -> SeedEntryResponse:
    """CI/test-only: append a ledger entry and update the cached balance.

    Gated by ENABLE_TEST_ENDPOINTS (never true in production, see Settings)
    so the Postman/Newman e2e suite can fund an account without a public
    deposit endpoint, which is out of scope by design (see requirements §1).
    """
    if not settings.enable_test_endpoints:
        raise HTTPException(status_code=404, detail="not_found")

    account = session.get(Account, payload.account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="not_found")

    account.balance += payload.amount
    session.add(Entry(account_id=payload.account_id, amount=payload.amount))
    session.add(account)
    session.commit()
    session.refresh(account)

    return SeedEntryResponse(account_id=account.id, balance=account.balance)
