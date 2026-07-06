"""phase ③ 에이전트 단위 테스트 (API 불필요 — Fake/Mock 클라이언트)."""

from __future__ import annotations

import json

from app.agent import analyze_query, resolve, run_agent
from app.agent.schemas import Route
from app.llm.mock import MockLLMClient


class FakeClient:
    """지정한 JSON 을 그대로 반환하는 결정적 클라이언트."""

    def __init__(self, payload: dict) -> None:
        self._text = json.dumps(payload, ensure_ascii=False)

    def generate_text(self, prompt, system=None, json=False) -> str:
        return self._text

    def generate_vision(self, prompt, image_paths, system=None, json=False) -> str:
        return self._text


_CLEAR = {
    "domain": "road",
    "intent": "포트홀 보수 절차 확인",
    "intent_type": "절차문의",
    "is_ambiguous": False,
    "ambiguity_score": 0.1,
    "missing_slots": [],
    "route": "hybrid",
    "keywords": ["포트홀", "보수 절차"],
    "rationale": "명확한 절차 문의",
}

_AMBIGUOUS = {
    "domain": "etc",
    "intent": "불명확",
    "intent_type": "기타",
    "is_ambiguous": True,
    "ambiguity_score": 0.9,
    "missing_slots": ["대상", "기간"],
    "route": "hybrid",
    "keywords": [],
    "rationale": "지시 대상 불명확",
}


def test_analyze_query_parses_and_validates_route():
    a = analyze_query("포트홀 보수", client=FakeClient(_CLEAR))
    assert a.domain == "road"
    assert a.route == "hybrid"
    assert a.keywords == ["포트홀", "보수 절차"]
    assert a.is_ambiguous is False


def test_analyze_query_invalid_route_falls_back_hybrid():
    payload = {**_CLEAR, "route": "banana"}
    a = analyze_query("x", client=FakeClient(payload))
    assert a.route == Route.HYBRID.value


def test_analyze_query_invalid_domain_falls_back_etc():
    payload = {**_CLEAR, "domain": "우주"}
    a = analyze_query("x", client=FakeClient(payload))
    assert a.domain == "etc"


def test_resolve_clear_uses_recommended_route():
    a = analyze_query("포트홀 보수", client=FakeClient(_CLEAR))
    r = resolve("포트홀 보수", a, threshold=0.5)
    assert r.route == "hybrid"
    assert r.template is None
    assert r.is_ambiguous is False


def test_resolve_ambiguous_returns_clarify_with_template():
    a = analyze_query("그거 어떻게", client=FakeClient(_AMBIGUOUS))
    r = resolve("그거 어떻게", a, threshold=0.5)
    assert r.route == Route.CLARIFY.value
    assert r.template is not None
    assert r.template["required"] == ["대상", "기간"]


def test_ambiguity_triggered_by_score_threshold():
    payload = {**_CLEAR, "is_ambiguous": False, "ambiguity_score": 0.8}
    a = analyze_query("x", client=FakeClient(payload))
    r = resolve("x", a, threshold=0.5)
    assert r.route == Route.CLARIFY.value


def test_run_agent_clear_via_graph():
    r = run_agent("포트홀 보수 절차", client=FakeClient(_CLEAR), threshold=0.5)
    assert r.route == "hybrid"
    assert r.template is None


def test_run_agent_ambiguous_via_graph():
    r = run_agent("그거 어떻게 해", client=FakeClient(_AMBIGUOUS), threshold=0.5)
    assert r.route == Route.CLARIFY.value
    assert r.template is not None


def test_run_agent_skip_clarify_forces_route():
    # 모호해도 skip_clarify=True 면 clarify 를 건너뛰고 라우팅 강행
    r = run_agent("그거 어떻게 해", client=FakeClient(_AMBIGUOUS), threshold=0.5, skip_clarify=True)
    assert r.route != Route.CLARIFY.value
    assert r.template is None


def test_analyze_query_with_mock_client_defaults():
    # MockLLMClient 는 에이전트 전용 필드가 없음 → 안전한 기본값으로 수렴
    a = analyze_query("교통 정체 원인", client=MockLLMClient())
    assert a.domain in {"road", "safety", "traffic", "etc"}
    assert a.route in {"vector", "keyword", "hybrid", "public_api"}
