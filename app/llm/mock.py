"""Mock LLM/VLM 클라이언트 — API/할당량 없이 파이프라인 구조를 검증하기 위한 대체 구현.

phase ① 의 HashingEmbedder 와 같은 역할(무비용 스탠드인). 결정적 응답을 돌려준다.
"""

from __future__ import annotations

import json


class MockLLMClient:
    def __init__(self, model: str = "mock") -> None:
        self.model = model

    def generate_text(
        self, prompt: str, system: str | None = None, json: bool = False
    ) -> str:
        if json:
            return _dumps(
                {
                    "unified_query": "[mock] " + " ".join(prompt.split())[:80],
                    "keywords": ["mock", "검색"],
                    "domain_hint": "etc",
                }
            )
        return "[mock-text] " + " ".join(prompt.split())[:120]

    def generate_vision(
        self,
        prompt: str,
        image_paths: list[str],
        system: str | None = None,
        json: bool = False,
    ) -> str:
        if json:
            return _dumps(
                {
                    "context_text": "[mock] 이미지에 도로 표면과 파손 흔적이 관찰됩니다.",
                    "labels": ["도로", "파손", "포트홀"],
                    "situation": "[mock] 노면 균열과 함몰이 보이는 상황",
                    "estimated_cause": "[mock] 반복 하중과 배수 불량 추정",
                }
            )
        return "[mock-vision] " + ",".join(image_paths)


def _dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False)
