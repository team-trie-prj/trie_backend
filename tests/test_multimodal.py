"""phase ② 멀티모달 질의 분석 단위 테스트 (API 불필요 — MockLLMClient)."""

from __future__ import annotations

from app.llm.base import parse_json_response
from app.llm.mock import MockLLMClient
from app.services.multimodal import (
    analyze_multimodal,
    extract_visual_context,
    merge_query,
)


def test_parse_json_response_variants():
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_response('{"b": 2}') == {"b": 2}
    assert parse_json_response('설명문 {"c": 3} 뒤에 잡텍스트') == {"c": 3}
    assert parse_json_response("") == {}
    assert parse_json_response("not json at all") == {}


def test_extract_visual_context_mock():
    vc = extract_visual_context("dummy.jpg", domain="road", client=MockLLMClient())
    assert isinstance(vc.labels, list) and vc.labels
    assert "도로" in vc.labels
    assert vc.context_text


def test_merge_query_mock():
    uq = merge_query("포트홀 신고 접수", domain="road", client=MockLLMClient())
    assert uq.unified_query
    assert isinstance(uq.keywords, list)
    assert uq.visual_context is None


def test_analyze_multimodal_text_only():
    uq = analyze_multimodal("교통 정체 원인 분석", client=MockLLMClient())
    assert uq.visual_context is None
    assert uq.unified_query


def test_analyze_multimodal_with_image():
    uq = analyze_multimodal(
        "이 도로 상태로 보고서 작성", image_path="x.jpg", domain="road", client=MockLLMClient()
    )
    assert uq.visual_context is not None
    assert uq.visual_context.labels
    # 병합 결과 dict 직렬화 확인
    d = uq.as_dict()
    assert d["visual_context"]["labels"]
    assert "raw" not in d["visual_context"]  # raw 는 응답에서 제외
