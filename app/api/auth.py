"""인증 API — 카카오 OAuth2 로그인 / 토큰 재발급(Silent Refresh) / 로그아웃 (김예담).

담당 요구사항(backend-speckit.md §1):
  - OAuth2 Authorization Code 로그인, 최초 저장/기존 동기화
  - JWT Access/Refresh 발급, Stateless, Refresh 재발급
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.auth import (
    AccessTokenResponse,
    KakaoLoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from ..security.deps import get_current_user_id
from ..services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/kakao", response_model=TokenResponse)
def kakao_login(body: KakaoLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """카카오 인가 코드로 로그인 → 사용자 동기화 → JWT 발급."""
    user, access_token, refresh_token, expires_in = auth_service.login_with_kakao(
        db, body.code, body.redirect_uri
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> AccessTokenResponse:
    """Refresh 토큰으로 Access 토큰 재발급 (Silent Refresh)."""
    access_token, expires_in = auth_service.refresh_access_token(db, body.refresh_token)
    return AccessTokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/logout")
def logout(
    user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)
) -> dict:
    """현재 사용자의 리프레시 토큰을 폐기."""
    auth_service.logout(db, user_id)
    return {"detail": "logged out"}
