"""API Key 관리 API — 등록/목록/삭제 (F5, 김예담).

평문은 응답에 노출하지 않으며(마스킹), 인증 필요. 응답은 공통 envelope 로 감싼다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..response import ApiResponse, ok
from ..schemas.apikey import ApiKeyCreate, ApiKeyMasked
from ..security.deps import get_current_user_id
from ..services import api_key_service

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiResponse[ApiKeyMasked])
def register_api_key(
    body: ApiKeyCreate,
    _uid: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    row = api_key_service.register(db, body.name, body.secret, body.provider, body.description)
    return ok(row, message="등록 완료")


@router.get("", response_model=ApiResponse[list[ApiKeyMasked]])
def list_api_keys(
    _uid: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    return ok(api_key_service.list_masked(db))


@router.delete("/{name}")
def delete_api_key(
    name: str,
    _uid: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    api_key_service.delete_api_key(db, name)
    return ok(data={"name": name}, message="deleted")
