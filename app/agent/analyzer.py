"""에이전트 핵심 분석 로직 (LLM 1회 호출 + 결정 후처리).

analyze_query : 도메인 태깅 + Intent + 모호성 + 라우팅 후보 + 키워드를 한 번에 구조화 추출.
resolve       : 모호하면 CLARIFY(+템플릿), 아니면 추천 라우팅으로 확정.
"""

from __future__ import annotations

from ..llm import get_llm_client, parse_json_response
from .schemas import VALID_ROUTES, AgentAnalysis, AgentResult, Route
from .templates import build_template

_SYSTEM = (
    "당신은 하이브리드 RAG 검색 에이전트입니다. 사용자 질의를 분석해 "
    "대상 도메인, 궁극적 의도, 모호성, 최적 검색 경로를 판단합니다."
)

_ROUTE_GUIDE = (
    "route 판단 기준:\n"
    "- keyword: 특정 문서명/조항/코드/고유명사의 정확 매칭이 핵심\n"
    "- vector: 개념·의미·유사 사례의 의미 기반 탐색\n"
    "- hybrid: 키워드 정확성과 의미 탐색이 모두 필요\n"
    "- public_api: 공공데이터 통계/실시간 수치(교통량·사고·중대재해 통계 등)가 필요"
)


def _prompt(query: str, domain_hint: str, image_context: str | None) -> str:
    ic = f"\n[이미지 맥락]\n{image_context}" if image_context else ""
    return (
        f"다음 질의를 분석해 JSON 으로만 답하세요.\n[질의]\n{query}{ic}\n"
        f"[도메인 힌트] {domain_hint}\n\n{_ROUTE_GUIDE}\n\n"
        "필드:\n"
        "- domain: road|safety|traffic|etc (자율 태깅)\n"
        "- intent: 사용자의 궁극적 의도 (1문장)\n"
        "- intent_type: 정보검색|통계조회|절차문의|보고서작성|기타\n"
        "- is_ambiguous: 질의가 모호하거나 필수 정보가 부족한가 (true/false)\n"
        "- ambiguity_score: 0.0~1.0 (모호할수록 높음)\n"
        "- missing_slots: 부족한 필수 정보 항목 배열\n"
        "- route: vector|keyword|hybrid|public_api\n"
        "- keywords: 핵심 키워드 배열\n"
        "- rationale: 판단 근거 (1문장)\n"
        "한국어로 작성."
    )


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(x) for x in value]
    return []


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def analyze_query(
    query: str,
    domain_hint: str = "etc",
    image_context: str | None = None,
    client=None,
) -> AgentAnalysis:
    client = client or get_llm_client()
    raw = client.generate_text(
        _prompt(query, domain_hint, image_context), system=_SYSTEM, json=True
    )
    data = parse_json_response(raw)

    route = str(data.get("route") or Route.HYBRID.value).lower()
    if route not in VALID_ROUTES or route == Route.CLARIFY.value:
        route = Route.HYBRID.value

    domain = str(data.get("domain") or domain_hint or "etc").lower()
    if domain not in {"road", "safety", "traffic", "etc"}:
        domain = "etc"

    return AgentAnalysis(
        domain=domain,
        intent=str(data.get("intent") or query).strip(),
        intent_type=str(data.get("intent_type") or "기타").strip(),
        is_ambiguous=bool(data.get("is_ambiguous", False)),
        ambiguity_score=_to_float(data.get("ambiguity_score"), 0.0),
        missing_slots=_as_list(data.get("missing_slots")),
        route=route,
        keywords=_as_list(data.get("keywords")),
        rationale=str(data.get("rationale") or "").strip(),
        raw=raw,
    )


def _base_result(query: str, analysis: AgentAnalysis, route: str, template) -> AgentResult:
    return AgentResult(
        query=query,
        domain=analysis.domain,
        intent=analysis.intent,
        intent_type=analysis.intent_type,
        route=route,
        is_ambiguous=(route == Route.CLARIFY.value),
        ambiguity_score=analysis.ambiguity_score,
        missing_slots=analysis.missing_slots,
        keywords=analysis.keywords,
        rationale=analysis.rationale,
        template=template,
    )


def build_clarify_result(query: str, analysis: AgentAnalysis) -> AgentResult:
    """모호 질의 → 검색 보류, 재질의 템플릿 제시."""
    template = build_template(analysis.domain, analysis.missing_slots)
    return _base_result(query, analysis, Route.CLARIFY.value, template)


def build_route_result(query: str, analysis: AgentAnalysis) -> AgentResult:
    """명확 질의 → 추천 라우팅 확정."""
    return _base_result(query, analysis, analysis.route, None)


def is_ambiguous(analysis: AgentAnalysis, threshold: float = 0.5) -> bool:
    return analysis.is_ambiguous or analysis.ambiguity_score >= threshold


def resolve(query: str, analysis: AgentAnalysis, threshold: float = 0.5) -> AgentResult:
    """모호성 판단 후 CLARIFY 또는 라우팅으로 확정 (선형 경로)."""
    if is_ambiguous(analysis, threshold):
        return build_clarify_result(query, analysis)
    return build_route_result(query, analysis)
