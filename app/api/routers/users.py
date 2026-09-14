"""Auth endpoints (requirements §3)."""

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_auth_service, get_user_service
from app.api.schemas.user import LoginResponse, UserCreateRequest, UserLoginRequest, UserResponse
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter(tags=["users"])


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    payload: UserCreateRequest, user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    user = user_service.register_user(
        username=payload.username,
        password=payload.password,
        full_name=payload.full_name,
        email=payload.email,
    )
    return UserResponse(
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        password_changed_at=user.password_changed_at,
        created_at=user.created_at,
    )


@router.post("/users/login", response_model=LoginResponse)
def login_user(
    payload: UserLoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    result = auth_service.login(
        username=payload.username,
        password=payload.password,
        user_agent=request.headers.get("user-agent", ""),
        client_ip=request.client.host if request.client else "",
    )
    return LoginResponse(
        session_id=str(result.session_id),
        access_token=result.access_token,
        access_token_expires_at=result.access_token_expires_at,
        refresh_token=result.refresh_token,
        refresh_token_expires_at=result.refresh_token_expires_at,
        user=UserResponse(
            username=result.user.username,
            full_name=result.user.full_name,
            email=result.user.email,
            password_changed_at=result.user.password_changed_at,
            created_at=result.user.created_at,
        ),
    )
