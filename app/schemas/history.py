"""검색 이력 스키마 (F8 확장)."""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class HistoryItem(BaseModel):
    """목록 요약(사이드바용)."""

    model_config = ConfigDict(from_attributes=True)

    session_uuid: str
    query: str
    domain: str | None = None
    created_at: datetime.datetime


class HistoryDetail(BaseModel):
    """스냅샷 복원용(질의 + 검색 결과)."""

    model_config = ConfigDict(from_attributes=True)

    session_uuid: str
    query: str
    domain: str | None = None
    result_snapshot: Any = None
    report_snapshot: Any = None
    created_at: datetime.datetime


class HistoryLogRequest(BaseModel):
    """명시적 이력 기록(FE 직접 호출용). 미들웨어 자동 로깅과 session_uuid 기준 upsert."""

    session_uuid: str
    query: str
    domain: str | None = None
    result_snapshot: dict | None = None
