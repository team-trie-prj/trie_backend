"""LLM / VLM 클라이언트 추상화.

- 기본 제공자: Google Gemini 무료 티어 (gemini-2.5-flash, 비전 지원).
- 대체: Mock(오프라인/테스트), Ollama(추후).
- 키가 없거나 provider=mock 이면 자동으로 MockLLMClient 로 폴백해 무비용 동작.
"""

from __future__ import annotations

from functools import lru_cache

from .base import LLMClient, parse_json_response
from .mock import MockLLMClient

__all__ = ["LLMClient", "MockLLMClient", "get_llm_client", "parse_json_response"]


@lru_cache
def get_llm_client() -> LLMClient:
    from ..config import get_settings

    settings = get_settings()

    if settings.llm_provider == "mock" or not settings.gemini_api_key:
        return MockLLMClient()

    if settings.llm_provider == "gemini":
        from .gemini import GeminiClient

        return GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.llm_model,
            vlm_model=settings.vlm_model,
        )

    if settings.llm_provider == "ollama":
        raise NotImplementedError("Ollama provider는 아직 미구현 (추후 로컬 VLM 연동)")

    raise ValueError(f"알 수 없는 LLM_PROVIDER: {settings.llm_provider}")
