"""민감정보(외부 API Key 등) 대칭 암호화 — Fernet (F5, 김예담).

- `APP_ENCRYPTION_KEY`(.env) 를 사용하고, 미설정 시 `JWT_SECRET_KEY` 에서 결정적으로 파생한다(dev 편의).
- 평문은 절대 저장/응답하지 않는다.
"""

from __future__ import annotations

import base64
import functools
import hashlib

from cryptography.fernet import Fernet

from ..config import get_settings


@functools.lru_cache(maxsize=1)
def _fernet() -> Fernet:
    """Fernet 인스턴스 캐시 — 호출마다 키 파생/객체 생성 방지."""
    settings = get_settings()
    key = settings.app_encryption_key
    if not key:
        key = base64.urlsafe_b64encode(
            hashlib.sha256(settings.jwt_secret_key.encode()).digest()
        ).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def mask(secret: str, shown: int = 4) -> str:
    """미리보기용 마스킹 (예: 'abcd••••'). 평문 대체 노출용."""
    if not secret:
        return ""
    if len(secret) <= shown:
        return secret[0] + "•••"
    return secret[:shown] + "•" * 4
