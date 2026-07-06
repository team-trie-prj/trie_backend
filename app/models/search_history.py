"""SearchHistory — 검색 세션 이력 로깅/복원 (F8 확장, 김예담).

vikira `/api/v1/search` 앞단 미들웨어가 매 검색을 여기에 기록(session_uuid 기준 upsert).
FE 이력 사이드바(FNC-HIS-01) 목록·스냅샷 복원의 SoT. FIFO 로 사용자별 상한 유지.
"""

from __future__ import annotations

import datetime

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ..utils import utcnow


class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    query: Mapped[str] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(16), nullable=True)
    result_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)   # 검색 스냅샷(입력·VLM 분석·공공 통계 포함)
    report_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 보고서 스냅샷
    created_at: Mapped[datetime.datetime] = mapped_column(default=utcnow, index=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=utcnow, onupdate=utcnow)
