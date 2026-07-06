"""멀티모달 분석 · 통합 검색 응답 스키마 (OpenAPI 용)."""

from __future__ import annotations

from pydantic import BaseModel


class VisualContextOut(BaseModel):
    context_text: str = ""
    labels: list[str] = []
    situation: str = ""
    estimated_cause: str = ""


class AnalyzeResponse(BaseModel):
    unified_query: str
    keywords: list[str] = []
    domain_hint: str = "etc"
    visual_context: VisualContextOut | None = None


class AgentOut(BaseModel):
    query: str
    domain: str
    intent: str
    intent_type: str
    route: str
    is_ambiguous: bool
    ambiguity_score: float
    missing_slots: list[str] = []
    keywords: list[str] = []
    rationale: str = ""
    template: dict | None = None


class SearchHitOut(BaseModel):
    source: str  # vector | keyword | public_api
    document_id: int | None = None
    chunk_index: int | None = None
    score: float
    domain: str = "etc"
    text: str
    stats: dict | None = None  # public_api 수치 데이터(선택)


class SearchResultOut(BaseModel):
    route: str
    query: str
    hits: list[SearchHitOut] = []
    used_tokens: int = 0
    truncated: bool = False
    note: str | None = None


class SearchResponse(BaseModel):
    session_id: str | None = None
    agent: AgentOut
    search: SearchResultOut | None = None
