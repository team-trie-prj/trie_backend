"""작업 13 — LLM 컨텍스트 한도 초과 방지용 데이터 절삭.

재정렬된 상위 청크를 토큰 예산 안에서 그리디하게 채운다.
(청킹의 estimate_tokens 재사용 — 토크나이저 없이 근사)
"""

from __future__ import annotations

from ..pipeline.chunking import estimate_tokens
from .schemas import SearchHit


def truncate_to_budget(
    hits: list[SearchHit],
    max_tokens: int,
    final_k: int | None = None,
) -> tuple[list[SearchHit], int, bool]:
    """반환: (선택된 hits, 사용 토큰 추정, 절삭 발생 여부)."""
    selected: list[SearchHit] = []
    used = 0
    truncated = False

    for hit in hits:
        if final_k is not None and len(selected) >= final_k:
            truncated = True
            break
        tokens = estimate_tokens(hit.text)
        if selected and used + tokens > max_tokens:
            truncated = True
            break
        selected.append(hit)
        used += tokens

    return selected, used, truncated
