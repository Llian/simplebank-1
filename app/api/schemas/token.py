from datetime import datetime

from pydantic import BaseModel


class RenewAccessRequest(BaseModel):
    refresh_token: str


class RenewAccessResponse(BaseModel):
    access_token: str
    access_token_expires_at: datetime
