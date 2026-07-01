"""작업 11 — Vector DB 코사인 거리 기반 의미 탐색.

BGE-m3 로 질의 임베딩 후 ChromaDB 코사인 공간에서 최근접 청크 조회.
코사인 거리(distance) → 유사도 점수(1 - distance)로 변환.
"""

from __future__ import annotations

from ..pipeline.embedding import get_embedder
from ..vectorstore import get_vector_store
from .schemas import SearchHit


def vector_search(
    query: str,
    domain: str | None = None,
    limit: int = 20,
    embedder=None,
    store=None,
) -> list[SearchHit]:
    embedder = embedder or get_embedder()
    store = store or get_vector_store()

    query_vec = embedder.embed_query(query)
    where = {"domain": domain} if domain and domain != "etc" else None
    res = store.query(query_vec, n_results=limit, where=where)

    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]

    hits: list[SearchHit] = []
    for id_, doc, dist, meta in zip(ids, docs, dists, metas, strict=False):
        meta = meta or {}
        hits.append(
            SearchHit(
                source="vector",
                document_id=meta.get("document_id"),
                chunk_index=meta.get("chunk_index"),
                text=doc or "",
                score=1.0 - float(dist),  # cosine distance → similarity
                domain=str(meta.get("domain", "etc")),
                vector_id=id_,
                meta=meta,
            )
        )
    return hits
