"""에이전트 오케스트레이션 — LangGraph StateGraph (미설치 시 선형 폴백).

흐름:  analyze ─┬─(모호)→ clarify → END
                 └─(명확)→ route   → END
"""

from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

from ..config import get_settings
from ..llm import get_llm_client
from .analyzer import (
    analyze_query,
    build_clarify_result,
    build_route_result,
    is_ambiguous,
    resolve,
)
from .schemas import AgentResult, Route

logger = logging.getLogger(__name__)
_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]{2,}")


class _AgentState(TypedDict, total=False):
    query: str
    domain_hint: str
    image_context: str | None
    analysis: Any
    result: AgentResult


def _fallback_result(query: str, domain_hint: str) -> AgentResult:
    """LLM 판단 에러/타임아웃 시 하이브리드 강제 라우팅 (S7 · FNC-SRC-02).

    LLM 없이도 동작하는 키워드+벡터 검색으로 이어지도록 route=hybrid 로 확정하고,
    키워드는 질의에서 규칙 기반으로 추출한다.
    """
    domain = domain_hint if domain_hint in {"road", "safety", "traffic", "etc"} else "etc"
    keywords = list(dict.fromkeys(_TOKEN_RE.findall(query)))[:8]
    return AgentResult(
        query=query,
        domain=domain,
        intent=query,
        intent_type="기타",
        route=Route.HYBRID.value,
        is_ambiguous=False,
        ambiguity_score=0.0,
        missing_slots=[],
        keywords=keywords,
        rationale="LLM 판단 에러/지연 — 하이브리드 폴백(S7)",
        template=None,
    )


def run_agent(
    query: str,
    domain_hint: str = "etc",
    image_context: str | None = None,
    client=None,
    threshold: float | None = None,
    skip_clarify: bool = False,
) -> AgentResult:
    """질의 → (도메인·의도·모호성·라우팅) 최종 결정.

    - skip_clarify=True : 모호 질의여도 재질의(clarify)를 건너뛰고 라우팅 강행.
    - LLM 판단 에러/타임아웃(S7, 60초) 시 하이브리드로 강제 폴백 → 500 대신 검색 지속.
    """
    client = client or get_llm_client()
    if threshold is None:
        threshold = get_settings().agent_ambiguity_threshold

    try:
        if skip_clarify:
            analysis = analyze_query(query, domain_hint, image_context, client)
            return build_route_result(query, analysis)

        graph = _try_build_graph(client, threshold)
        if graph is not None:
            state = graph.invoke(
                {"query": query, "domain_hint": domain_hint, "image_context": image_context}
            )
            return state["result"]

        # LangGraph 미설치 시 선형 폴백
        analysis = analyze_query(query, domain_hint, image_context, client)
        return resolve(query, analysis, threshold)
    except Exception as exc:  # noqa: BLE001 — 어떤 LLM 실패든 하이브리드로 폴백
        logger.warning("run_agent LLM 판단 실패 → 하이브리드 폴백: %s", exc)
        return _fallback_result(query, domain_hint)


def _try_build_graph(client, threshold: float):
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    def node_analyze(state: _AgentState) -> dict:
        analysis = analyze_query(
            state["query"],
            state.get("domain_hint", "etc"),
            state.get("image_context"),
            client,
        )
        return {"analysis": analysis}

    def branch(state: _AgentState) -> str:
        return "clarify" if is_ambiguous(state["analysis"], threshold) else "route"

    def node_clarify(state: _AgentState) -> dict:
        return {"result": build_clarify_result(state["query"], state["analysis"])}

    def node_route(state: _AgentState) -> dict:
        return {"result": build_route_result(state["query"], state["analysis"])}

    graph = StateGraph(_AgentState)
    graph.add_node("analyze", node_analyze)
    graph.add_node("clarify", node_clarify)
    graph.add_node("route", node_route)
    graph.set_entry_point("analyze")
    graph.add_conditional_edges("analyze", branch, {"clarify": "clarify", "route": "route"})
    graph.add_edge("clarify", END)
    graph.add_edge("route", END)
    return graph.compile()
