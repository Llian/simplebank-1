"""Token-renewal endpoint (requirements §3)."""

from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service
from app.api.schemas.token import RenewAccessRequest, RenewAccessResponse
from app.services.auth_service import AuthService

router = APIRouter(tags=["tokens"])


@router.post("/tokens/renew_access", response_model=RenewAccessResponse)
def renew_access(
    payload: RenewAccessRequest, auth_service: AuthService = Depends(get_auth_service)
) -> RenewAccessResponse:
    result = auth_service.renew_access_token(refresh_token=payload.refresh_token)
    return RenewAccessResponse(
        access_token=result.access_token, access_token_expires_at=result.access_token_expires_at
    )
