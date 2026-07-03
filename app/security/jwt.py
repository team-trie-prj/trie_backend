"""JWT 발급/검증 — python-jose, HS256 (Stateless 인증).

Access / Refresh 두 종류를 `type` 클레임으로 구분한다.
"""

from __future__ import annotations

import datetime
import uuid

from jose import jwt

from ..config import get_settings
from ..utils import utcnow

ACCESS = "access"
REFRESH = "refresh"


def _epoch(dt: datetime.datetime) -> int:
    """naive UTC datetime → epoch seconds."""
    return int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())


def _encode(user_id: int, token_type: str, delta: datetime.timedelta) -> tuple[str, datetime.datetime]:
    settings = get_settings()
    now = utcnow()
    exp = now + delta
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": _epoch(now),
        "exp": _epoch(exp),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, exp


def create_access_token(user_id: int) -> tuple[str, int]:
    """(access_token, expires_in[sec]) 반환."""
    settings = get_settings()
    token, _ = _encode(
        user_id, ACCESS, datetime.timedelta(minutes=settings.access_token_expire_minutes)
    )
    return token, settings.access_token_expire_minutes * 60


def create_refresh_token(user_id: int) -> tuple[str, datetime.datetime]:
    """(refresh_token, 만료 datetime[naive UTC]) 반환 — 만료는 DB 저장용."""
    settings = get_settings()
    return _encode(
        user_id, REFRESH, datetime.timedelta(days=settings.refresh_token_expire_days)
    )


def decode_token(token: str) -> dict:
    """서명·만료 검증 후 payload 반환. 실패 시 jose.exceptions.JWTError 계열 발생."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
