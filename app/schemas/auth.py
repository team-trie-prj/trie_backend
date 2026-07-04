"""인증 요청/응답 스키마 (김예담)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class KakaoLoginRequest(BaseModel):
    code: str
    redirect_uri: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None = None
    provider: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
