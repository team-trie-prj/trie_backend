"""API Key 서비스 — 암호화 저장/조회/목록/삭제 (F5, 김예담).

- 저장: Fernet 암호화 후 RDBMS.
- 복호화(get_secret): 서버 내부에서만 사용(예: F10 공공 API 호출). 응답 노출 금지.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ApiKey
from ..schemas.apikey import ApiKeyMasked
from ..security.crypto import decrypt, encrypt, mask


def _to_masked(row: ApiKey) -> ApiKeyMasked:
    return ApiKeyMasked(
        name=row.name,
        provider=row.provider,
        secret_preview=mask(decrypt(row.secret_encrypted)),
        description=row.description,
        updated_at=row.updated_at,
    )


def register(
    db: Session,
    name: str,
    secret: str,
    provider: str | None = None,
    description: str | None = None,
) -> ApiKeyMasked:
    """API Key 등록/갱신(upsert). 평문은 암호화하여 저장."""
    row = db.scalar(select(ApiKey).where(ApiKey.name == name))
    enc = encrypt(secret)
    if row is None:
        row = ApiKey(name=name, provider=provider, secret_encrypted=enc, description=description)
        db.add(row)
    else:
        row.secret_encrypted = enc
        if provider is not None:
            row.provider = provider
        if description is not None:
            row.description = description
    db.commit()
    db.refresh(row)
    return _to_masked(row)


def list_masked(db: Session) -> list[ApiKeyMasked]:
    rows = db.scalars(select(ApiKey).order_by(ApiKey.name)).all()
    return [_to_masked(r) for r in rows]


def get_secret(db: Session, name: str) -> str:
    """서버 내부용 평문 복호화. (절대 응답에 노출 금지)"""
    row = db.scalar(select(ApiKey).where(ApiKey.name == name))
    if row is None:
        raise HTTPException(status_code=404, detail="API Key 를 찾을 수 없습니다.")
    return decrypt(row.secret_encrypted)


def delete_api_key(db: Session, name: str) -> None:
    row = db.scalar(select(ApiKey).where(ApiKey.name == name))
    if row is None:
        raise HTTPException(status_code=404, detail="API Key 를 찾을 수 없습니다.")
    db.delete(row)
    db.commit()
