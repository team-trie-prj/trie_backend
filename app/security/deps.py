"""FastAPI 인증 의존성 — Bearer Access Token 검증."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose.exceptions import ExpiredSignatureError, JWTError

from .jwt import ACCESS, decode_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> int:
    """유효한 Access 토큰의 사용자 id(Long) 반환. 실패 시 401."""
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="인증 정보가 없습니다.")
    try:
        payload = decode_token(creds.credentials)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="액세스 토큰이 만료되었습니다.")
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    if payload.get("type") != ACCESS:
        raise HTTPException(status_code=401, detail="액세스 토큰이 아닙니다.")
    return int(payload["sub"])
