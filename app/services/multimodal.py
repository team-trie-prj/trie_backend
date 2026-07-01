"""② 멀티모달 질의 분석  (FNC-SRC-01)

- extract_visual_context : VLM 이미지 시각적 맥락 추출
    · 현장 이미지 → 맥락 설명 / 라벨(위험요소·객체) / 상황 요약 / 추정 원인 (구조화 JSON)
- merge_query           : 텍스트 질의 + 이미지 맥락 논리적 병합(프롬프팅)
    · 사용자 자연어 + 이미지 분석 → 하이브리드 검색용 '통합 쿼리' + 키워드 + 도메인 힌트
- analyze_multimodal    : 위 둘을 잇는 오케스트레이션

LLM/VLM 은 무료 Gemini(gemini-2.5-flash). 키가 없으면 MockLLMClient 로 폴백.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..llm import get_llm_client, parse_json_response

# 도메인별 분석 관점 (에이전트 단계의 '도메인 자율 태깅' 과 연동될 힌트)
DOMAIN_HINTS = {
    "road": "도로 시설물 — 포트홀, 균열, 침하, 표지판/신호등 손상, 노면 표시 마모 등",
    "safety": "산업안전 — 보호구(안전모/안전대) 미착용, 위험 설비, 추락/끼임/전도 위험 등",
    "traffic": "교통 — 차량 정체, 사고, 신호 위반, CCTV 스냅샷 내 이상 상황 등",
    "etc": "일반 현장 상황",
}

_VLM_SYSTEM = (
    "당신은 도로·산업안전·교통 현장 점검 이미지를 분석하는 전문가입니다. "
    "이미지에서 실제로 관찰되는 사실만 근거로, 과장 없이 한국어로 분석합니다."
)

_MERGE_SYSTEM = (
    "당신은 하이브리드 검색(RAG)을 위한 검색 쿼리 설계 전문가입니다. "
    "사용자 의도와 이미지 맥락을 논리적으로 결합해 검색에 최적화된 통합 쿼리를 만듭니다."
)


@dataclass
class VisualContext:
    context_text: str = ""
    labels: list[str] = field(default_factory=list)
    situation: str = ""
    estimated_cause: str = ""
    raw: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


@dataclass
class UnifiedQuery:
    unified_query: str
    keywords: list[str] = field(default_factory=list)
    domain_hint: str = "etc"
    visual_context: VisualContext | None = None

    def as_dict(self) -> dict:
        return {
            "unified_query": self.unified_query,
            "keywords": self.keywords,
            "domain_hint": self.domain_hint,
            "visual_context": self.visual_context.as_dict() if self.visual_context else None,
        }


def _vlm_prompt(domain: str) -> str:
    hint = DOMAIN_HINTS.get(domain, DOMAIN_HINTS["etc"])
    return (
        "다음 현장 이미지를 분석해 JSON 으로만 답하세요.\n"
        f"분석 관점(도메인): {hint}\n\n"
        "필드:\n"
        "- context_text: 이미지 전반의 시각적 맥락 설명 (2~3문장)\n"
        "- labels: 핵심 객체/위험요소 키워드 배열 (문자열 배열)\n"
        "- situation: 상황 요약 (1문장)\n"
        "- estimated_cause: 추정 원인 (1문장, 불명확하면 '판단 불가')\n"
        "모든 값은 한국어로 작성."
    )


def extract_visual_context(
    image_path: str, domain: str = "etc", client=None
) -> VisualContext:
    """VLM 으로 이미지의 시각적 맥락을 구조화 추출."""
    client = client or get_llm_client()
    raw = client.generate_vision(
        _vlm_prompt(domain), [image_path], system=_VLM_SYSTEM, json=True
    )
    data = parse_json_response(raw)
    labels = data.get("labels") or []
    if isinstance(labels, str):
        labels = [labels]
    return VisualContext(
        context_text=str(data.get("context_text", "")).strip(),
        labels=[str(x) for x in labels],
        situation=str(data.get("situation", "")).strip(),
        estimated_cause=str(data.get("estimated_cause", "")).strip(),
        raw=raw,
    )


def _merge_prompt(text_query: str, vc: VisualContext | None, domain: str) -> str:
    block = ""
    if vc:
        block = (
            "\n\n[이미지 분석 결과]\n"
            f"- 맥락: {vc.context_text}\n"
            f"- 라벨: {', '.join(vc.labels)}\n"
            f"- 상황: {vc.situation}\n"
            f"- 추정 원인: {vc.estimated_cause}"
        )
    return (
        "사용자 질의와 (있다면) 이미지 분석 결과를 논리적으로 병합하여, "
        "하이브리드 검색에 사용할 통합 쿼리를 JSON 으로만 생성하세요.\n"
        f"\n[사용자 질의]\n{text_query}{block}\n\n"
        "필드:\n"
        "- unified_query: 검색용 자연어 통합 질의 (1~2문장, 이미지 맥락 반영)\n"
        "- keywords: 키워드/정규식 검색용 핵심어 배열 (문자열 배열)\n"
        "- domain_hint: road | safety | traffic | etc 중 하나\n"
        "한국어로 작성."
    )


def merge_query(
    text_query: str,
    visual_context: VisualContext | None = None,
    domain: str = "etc",
    client=None,
) -> UnifiedQuery:
    """텍스트 질의 + 이미지 맥락을 통합 쿼리로 병합."""
    client = client or get_llm_client()
    raw = client.generate_text(
        _merge_prompt(text_query, visual_context, domain), system=_MERGE_SYSTEM, json=True
    )
    data = parse_json_response(raw)
    keywords = data.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [keywords]
    return UnifiedQuery(
        unified_query=str(data.get("unified_query") or text_query).strip(),
        keywords=[str(x) for x in keywords],
        domain_hint=str(data.get("domain_hint") or domain),
        visual_context=visual_context,
    )


def analyze_multimodal(
    text_query: str,
    image_path: str | None = None,
    domain: str = "etc",
    client=None,
) -> UnifiedQuery:
    """멀티모달 질의 분석 오케스트레이션: (이미지 → 맥락) → 텍스트와 병합 → 통합 쿼리."""
    client = client or get_llm_client()
    vc = extract_visual_context(image_path, domain, client) if image_path else None
    return merge_query(text_query, vc, domain, client)
