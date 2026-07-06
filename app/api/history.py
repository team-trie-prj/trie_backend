"""검색 이력 API — 목록/스냅샷 복원/삭제/명시 기록 (F8 확장, 김예담, FNC-HIS-01).

자동 로깅은 vikira `/search` 앞단 미들웨어가 수행. 본 라우터는 조회·복원·삭제 + 명시 기록.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..response import ApiResponse, ok
from ..schemas.history import HistoryDetail, HistoryItem, HistoryLogRequest
from ..security.deps import get_current_user_id
from ..services import history_service

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=ApiResponse[list[HistoryItem]])
def list_history(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """현재 사용자의 검색 이력 목록(최신순)."""
    return ok(history_service.list_for_user(db, user_id))


@router.get("/{session_uuid}", response_model=ApiResponse[HistoryDetail])
def get_history(
    session_uuid: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """세션 스냅샷 복원(질의 + 검색 결과)."""
    return ok(history_service.get_for_user(db, session_uuid, user_id))


@router.post("", response_model=ApiResponse[HistoryDetail])
def log_history(
    body: HistoryLogRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """명시적 이력 기록(FE 직접 호출). session_uuid 기준 upsert."""
    row = history_service.record(
        db, body.session_uuid, body.query, body.domain, body.result_snapshot, user_id
    )
    return ok(row, message="기록됨")


@router.delete("/{session_uuid}")
def delete_history(
    session_uuid: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    history_service.delete_for_user(db, session_uuid, user_id)
    return ok(data={"session_uuid": session_uuid}, message="deleted")
