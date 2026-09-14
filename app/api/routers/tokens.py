"""Token-renewal endpoint (requirements §3). Dummy response — no service/repository layer yet."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.schemas.token import RenewAccessRequest, RenewAccessResponse

router = APIRouter(tags=["tokens"])


@router.post("/tokens/renew_access", response_model=RenewAccessResponse)
def renew_access(payload: RenewAccessRequest) -> RenewAccessResponse:
    return RenewAccessResponse(
        access_token="dummy-access-token",  # noqa: S106  # nosec B106 -- placeholder, not a secret
        access_token_expires_at=datetime.now(UTC),
    )
