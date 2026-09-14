"""Auth endpoints (requirements §3). Dummy responses — no service/repository layer yet."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.schemas.user import LoginResponse, UserCreateRequest, UserLoginRequest, UserResponse

router = APIRouter(tags=["users"])


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(payload: UserCreateRequest) -> UserResponse:
    return UserResponse(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        password_changed_at=datetime.fromtimestamp(0, tz=UTC),
        created_at=datetime.now(UTC),
    )


@router.post("/users/login", response_model=LoginResponse)
def login_user(payload: UserLoginRequest) -> LoginResponse:
    now = datetime.now(UTC)
    return LoginResponse(
        session_id="00000000-0000-0000-0000-000000000000",
        access_token="dummy-access-token",  # noqa: S106 -- placeholder, not a secret
        access_token_expires_at=now,
        refresh_token="dummy-refresh-token",  # noqa: S106 -- placeholder, not a secret
        refresh_token_expires_at=now,
        user=UserResponse(
            username=payload.username,
            full_name="Dummy User",
            email="dummy@example.com",
            password_changed_at=datetime.fromtimestamp(0, tz=UTC),
            created_at=now,
        ),
    )
