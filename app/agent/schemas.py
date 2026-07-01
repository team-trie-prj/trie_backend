"""에이전트 스키마 (도메인/라우팅/분석 결과)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class Route(str, Enum):
    VECTOR = "vector"  # 의미 기반 (ChromaDB 코사인)
    KEYWORD = "keyword"  # RDBMS 키워드/정규식 (BM25 성격)
    HYBRID = "hybrid"  # 키워드 + 벡터
    PUBLIC_API = "public_api"  # 공공데이터 통계/실시간
    CLARIFY = "clarify"  # 모호 → 재질의 템플릿


VALID_ROUTES = {r.value for r in Route}


@dataclass
class AgentAnalysis:
    """LLM 1회 분석 산출물."""

    domain: str = "etc"
    intent: str = ""
    intent_type: str = ""
    is_ambiguous: bool = False
    ambiguity_score: float = 0.0
    missing_slots: list[str] = field(default_factory=list)
    route: str = Route.HYBRID.value
    keywords: list[str] = field(default_factory=list)
    rationale: str = ""
    raw: str = ""


@dataclass
class AgentResult:
    """후처리까지 끝난 에이전트 최종 결정."""

    query: str
    domain: str
    intent: str
    intent_type: str
    route: str
    is_ambiguous: bool
    ambiguity_score: float
    missing_slots: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    rationale: str = ""
    template: dict | None = None  # route == clarify 일 때 재질의 템플릿

    def as_dict(self) -> dict:
        return asdict(self)
