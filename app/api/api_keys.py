"""API Key 관리 API — 등록/목록/삭제 (F5, 김예담).

평문은 응답에 노출하지 않으며(마스킹), 인증 필요.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.apikey import ApiKeyCreate, ApiKeyMasked
from ..security.deps import get_current_user_id
from ..services import api_key_service

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyMasked)
def register_api_key(
    body: ApiKeyCreate,
    _uid: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ApiKeyMasked:
    return api_key_service.register(db, body.name, body.secret, body.provider, body.description)


@router.get("", response_model=list[ApiKeyMasked])
def list_api_keys(
    _uid: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[ApiKeyMasked]:
    return api_key_service.list_masked(db)


@router.delete("/{name}")
def delete_api_key(
    name: str,
    _uid: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    api_key_service.delete_api_key(db, name)
    return {"detail": "deleted", "name": name}
