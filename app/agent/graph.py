"""에이전트 오케스트레이션 — LangGraph StateGraph (미설치 시 선형 폴백).

흐름:  analyze ─┬─(모호)→ clarify → END
                 └─(명확)→ route   → END
"""

from __future__ import annotations

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
from .schemas import AgentResult


class _AgentState(TypedDict, total=False):
    query: str
    domain_hint: str
    image_context: str | None
    analysis: Any
    result: AgentResult


def run_agent(
    query: str,
    domain_hint: str = "etc",
    image_context: str | None = None,
    client=None,
    threshold: float | None = None,
) -> AgentResult:
    """질의 → (도메인·의도·모호성·라우팅) 최종 결정."""
    client = client or get_llm_client()
    if threshold is None:
        threshold = get_settings().agent_ambiguity_threshold

    graph = _try_build_graph(client, threshold)
    if graph is not None:
        state = graph.invoke(
            {"query": query, "domain_hint": domain_hint, "image_context": image_context}
        )
        return state["result"]

    # LangGraph 미설치 시 선형 폴백
    analysis = analyze_query(query, domain_hint, image_context, client)
    return resolve(query, analysis, threshold)


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
