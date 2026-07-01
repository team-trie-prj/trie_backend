"""보고서 생성 요청/응답 스키마."""

from __future__ import annotations

import datetime

from pydantic import BaseModel

from .search import SearchHitOut


class ReportRequest(BaseModel):
    query: str
    domain: str = "etc"
    # inspection_log | complaint_brief | improvement_reco | situation_brief
    report_type: str = "inspection_log"
    session_id: str | None = None
    # 생략 시 서버가 query 로 재검색해 근거를 확보
    hits: list[SearchHitOut] | None = None


class ReportResponse(BaseModel):
    id: int | None = None
    session_id: str
    domain: str
    report_type: str
    content: str  # Markdown
    sources: list[dict] = []
    created_at: datetime.datetime | None = None
