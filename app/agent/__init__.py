"""③ 에이전트 — 도메인 태깅 · Intent 분석 · 모호성 평가 · RAG 라우팅  (FNC-SRC-02)

LLM 에이전트가 질의를 분석해 (1) 대상 도메인 자율 태깅, (2) 궁극적 의도 분석,
(3) 질의 모호성 평가(Low-context Detection), (4) 하이브리드 탐색 경로 자율 선택.
모호하면 검색을 보류하고 맞춤형 재질의 템플릿을 제시한다.
"""

from .analyzer import (
    analyze_query,
    build_clarify_result,
    build_route_result,
    resolve,
)
from .graph import run_agent
from .schemas import AgentAnalysis, AgentResult, Route

__all__ = [
    "AgentAnalysis",
    "AgentResult",
    "Route",
    "analyze_query",
    "resolve",
    "build_clarify_result",
    "build_route_result",
    "run_agent",
]
