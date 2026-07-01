"""④ 검색 실행 오케스트레이션.

에이전트 라우팅 결정을 받아 실제 검색을 수행:
  route=vector      → 벡터 코사인 의미 탐색
  route=keyword     → RDBMS 키워드/정규식 정밀 탐색
  route=hybrid      → 둘 다 → 중복 제거 → Cross-Encoder 재정렬
  route=public_api  → 공공데이터 API (김예담 모듈 위임 — 여기선 note 반환)
  route=clarify     → 검색 보류 (재질의 템플릿 필요)
마지막에 컨텍스트 토큰 예산으로 절삭한다.
"""

from __future__ import annotations

from ..agent.schemas import Route
from ..config import get_settings
from ..search.keyword import keyword_search
from ..search.rerank import rerank
from ..search.schemas import SearchHit, SearchResult
from ..search.truncate import truncate_to_budget
from ..search.vector import vector_search


def _dedup(hits: list[SearchHit]) -> list[SearchHit]:
    best: dict[tuple, SearchHit] = {}
    for hit in hits:
        k = hit.key()
        if k not in best or hit.score > best[k].score:
            best[k] = hit
    return list(best.values())


def execute_search(
    query: str,
    route: str,
    keywords: list[str] | None = None,
    domain: str | None = None,
    db=None,
    regex: str | None = None,
    top_k: int | None = None,
    final_k: int | None = None,
    rerank_backend: str | None = None,
    rerank_model: str | None = None,
) -> SearchResult:
    settings = get_settings()
    top_k = top_k or settings.search_top_k
    final_k = final_k or settings.search_final_k
    rerank_backend = rerank_backend or settings.rerank_backend
    rerank_model = rerank_model or settings.rerank_model

    if route == Route.CLARIFY.value:
        return SearchResult(
            route=route, query=query, note="모호 질의 — 재질의 템플릿 필요(검색 보류)"
        )
    if route == Route.PUBLIC_API.value:
        return SearchResult(
            route=route, query=query, note="공공데이터 API 실행은 김예담 모듈에 위임"
        )

    hits: list[SearchHit] = []
    if route in (Route.VECTOR.value, Route.HYBRID.value):
        hits += vector_search(query, domain=domain, limit=top_k)
    if route in (Route.KEYWORD.value, Route.HYBRID.value):
        hits += keyword_search(keywords or [query], domain=domain, db=db, limit=top_k, regex=regex)

    hits = _dedup(hits)
    hits = rerank(query, hits, backend=rerank_backend, model=rerank_model)
    selected, used, truncated = truncate_to_budget(hits, settings.context_max_tokens, final_k)

    return SearchResult(
        route=route, query=query, hits=selected, used_tokens=used, truncated=truncated
    )
