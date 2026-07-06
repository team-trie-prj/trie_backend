"""검색 이력 서비스 — 로깅(upsert)·조회·복원·삭제 + FIFO (F8 확장, 김예담)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import SearchHistory


def record(
    db: Session,
    session_uuid: str,
    query: str,
    domain: str | None,
    result_snapshot: Any,
    user_id: int | None = None,
) -> SearchHistory:
    """session_uuid 기준 upsert(미들웨어/명시 호출 중복 방지) + FIFO 정리."""
    row = db.scalar(select(SearchHistory).where(SearchHistory.session_uuid == session_uuid))
    if row is None:
        row = SearchHistory(
            session_uuid=session_uuid, user_id=user_id, query=query,
            domain=domain, result_snapshot=result_snapshot or {},
        )
        db.add(row)
    else:
        if query:
            row.query = query
        if domain is not None:
            row.domain = domain
        if result_snapshot:
            row.result_snapshot = result_snapshot
        if user_id is not None:
            row.user_id = user_id
    db.commit()
    db.refresh(row)
    _fifo_trim(db, row.user_id)
    return row


def _fifo_trim(db: Session, user_id: int | None) -> None:
    """사용자별 상한 초과 시 오래된 항목부터 삭제(FIFO)."""
    if user_id is None:
        return
    max_n = get_settings().history_max_per_user
    ids = db.scalars(
        select(SearchHistory.id)
        .where(SearchHistory.user_id == user_id)
        .order_by(SearchHistory.id.desc())
    ).all()
    extra = list(ids[max_n:])
    if extra:
        db.execute(delete(SearchHistory).where(SearchHistory.id.in_(extra)))
        db.commit()


def list_for_user(db: Session, user_id: int) -> list[SearchHistory]:
    return list(
        db.scalars(
            select(SearchHistory)
            .where(SearchHistory.user_id == user_id)
            .order_by(SearchHistory.id.desc())
        ).all()
    )


def get_for_user(db: Session, session_uuid: str, user_id: int) -> SearchHistory:
    row = db.scalar(
        select(SearchHistory).where(
            SearchHistory.session_uuid == session_uuid,
            SearchHistory.user_id == user_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="검색 이력을 찾을 수 없습니다.")
    return row


def delete_for_user(db: Session, session_uuid: str, user_id: int) -> None:
    row = get_for_user(db, session_uuid, user_id)
    db.delete(row)
    db.commit()
