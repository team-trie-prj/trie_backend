"""작업 14 — Cross-Encoder 기반 다중 출처 데이터 재정렬.

벡터/키워드 등 서로 다른 출처의 후보를 (query, chunk) 쌍으로 Cross-Encoder 에 넣어
직접 관련도를 산출하고 통합 재순위한다. 기본 모델: BAAI/bge-reranker-v2-m3 (로컬/무료).
backend="none" 이면 기존 점수 순서를 유지(테스트/오프라인).
"""

from __future__ import annotations

from functools import lru_cache

from .schemas import SearchHit


@lru_cache
def _get_reranker(model: str):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model)


def rerank(
    query: str,
    hits: list[SearchHit],
    backend: str = "cross-encoder",
    model: str = "BAAI/bge-reranker-v2-m3",
    top_k: int | None = None,
) -> list[SearchHit]:
    if not hits:
        return hits

    if backend == "cross-encoder":
        cross_encoder = _get_reranker(model)
        scores = cross_encoder.predict([(query, h.text) for h in hits])
        for hit, score in zip(hits, scores, strict=False):
            hit.score = float(score)

    ranked = sorted(hits, key=lambda h: h.score, reverse=True)
    return ranked[:top_k] if top_k else ranked
