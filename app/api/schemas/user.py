from datetime import datetime

from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    username: str
    password: str
    full_name: str
    email: str


class UserResponse(BaseModel):
    username: str
    full_name: str
    email: str
    password_changed_at: datetime
    created_at: datetime


class UserLoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    session_id: str
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime
    user: UserResponse
