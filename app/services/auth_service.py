"""인증 서비스 — 카카오 OAuth2 로그인 · JWT 발급/갱신/로그아웃 (김예담).

AI 추론과 무관하며 vikira 파이프라인을 호출하지 않는다.
카카오 자격증명(client_id) 미설정 시 mock 프로필로 폴백해 오프라인 개발/테스트가 가능하다.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import HTTPException
from jose.exceptions import ExpiredSignatureError, JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import RefreshToken, User
from ..security.jwt import (
    REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
)


@dataclass
class OAuthProfile:
    provider: str
    provider_id: str
    name: str
    email: str | None = None


def _fetch_kakao_profile(code: str, redirect_uri: str | None) -> OAuthProfile:
    """인가 코드 → 카카오 토큰 교환 → 사용자 정보 조회. (mock 폴백 지원)"""
    settings = get_settings()

    if settings.resolved_auth_provider == "mock":
        pid = f"mock_{abs(hash(code)) % 10_000_000}"
        return OAuthProfile("kakao", pid, "테스트사용자", f"{pid}@example.com")

    token_res = httpx.post(
        settings.kakao_token_url,
        data={
            "grant_type": "authorization_code",
            "client_id": settings.kakao_client_id,
            "client_secret": settings.kakao_client_secret,
            "redirect_uri": redirect_uri or settings.kakao_redirect_uri,
            "code": code,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10.0,
    )
    if token_res.status_code != 200:
        raise HTTPException(status_code=401, detail="카카오 인가 코드 검증에 실패했습니다.")
    kakao_access = token_res.json().get("access_token")

    me = httpx.get(
        settings.kakao_userinfo_url,
        headers={"Authorization": f"Bearer {kakao_access}"},
        timeout=10.0,
    )
    if me.status_code != 200:
        raise HTTPException(status_code=502, detail="카카오 사용자 정보 조회에 실패했습니다.")

    data = me.json()
    account = data.get("kakao_account", {})
    profile = account.get("profile", {})
    return OAuthProfile(
        provider="kakao",
        provider_id=str(data.get("id")),
        name=profile.get("nickname") or "카카오사용자",
        email=account.get("email"),
    )


def _upsert_user(db: Session, prof: OAuthProfile) -> User:
    """최초 로그인 시 저장, 기존 사용자면 정보 동기화."""
    user = db.scalar(
        select(User).where(
            User.provider == prof.provider, User.provider_id == prof.provider_id
        )
    )
    if user is None:
        user = User(
            provider=prof.provider,
            provider_id=prof.provider_id,
            name=prof.name,
            email=prof.email,
        )
        db.add(user)
    else:
        user.name = prof.name
        user.email = prof.email
    db.flush()
    return user


def login_with_kakao(
    db: Session, code: str, redirect_uri: str | None
) -> tuple[User, str, str, int]:
    """카카오 로그인 전체 플로우 → (user, access, refresh, expires_in)."""
    prof = _fetch_kakao_profile(code, redirect_uri)
    user = _upsert_user(db, prof)

    access_token, expires_in = create_access_token(user.id)
    refresh_token, refresh_exp = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token=refresh_token, expired_at=refresh_exp))
    db.commit()
    db.refresh(user)
    return user, access_token, refresh_token, expires_in


def refresh_access_token(db: Session, refresh_token: str) -> tuple[str, int]:
    """Refresh 토큰 검증(서명·만료·DB·폐기여부) 후 새 Access 발급 → (access, expires_in)."""
    try:
        payload = decode_token(refresh_token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="리프레시 토큰이 만료되었습니다.")
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다.")

    if payload.get("type") != REFRESH:
        raise HTTPException(status_code=401, detail="리프레시 토큰이 아닙니다.")

    row = db.scalar(select(RefreshToken).where(RefreshToken.token == refresh_token))
    if row is None or row.revoked:
        raise HTTPException(status_code=401, detail="폐기되었거나 알 수 없는 리프레시 토큰입니다.")

    access_token, expires_in = create_access_token(int(payload["sub"]))
    return access_token, expires_in


def logout(db: Session, user_id: int) -> None:
    """해당 사용자의 모든 리프레시 토큰 폐기 (Stateless access 는 만료까지 유효)."""
    rows = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)
        )
    ).all()
    for row in rows:
        row.revoked = True
    db.commit()
