"""LLM 클라이언트 프로토콜 + 공용 JSON 파싱 유틸."""

from __future__ import annotations

import json
import re
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def generate_text(
        self, prompt: str, system: str | None = None, json: bool = False
    ) -> str: ...

    def generate_vision(
        self,
        prompt: str,
        image_paths: list[str],
        system: str | None = None,
        json: bool = False,
    ) -> str: ...


def parse_json_response(text: str) -> dict:
    """LLM 응답 문자열에서 JSON 객체를 관대하게 추출.

    JSON 모드면 순수 JSON 이지만, 마크다운 펜스(```json)나 잡텍스트가 섞여도 복구한다.
    """
    if not text:
        return {}
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    try:
        return json.loads(t)
    except Exception:
        match = re.search(r"\{.*\}", t, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return {}
        return {}
