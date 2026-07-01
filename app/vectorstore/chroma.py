"""⑤ Vector DB (ChromaDB) 인덱싱 및 청크 적재

- 영속(PersistentClient) 컬렉션, 코사인 거리 공간(hnsw:space=cosine) 사용.
  → 이후 '⑪ Vector DB 코사인 거리 기반 의미 탐색' 작업이 이 컬렉션을 그대로 조회한다.
- 임베딩은 파이프라인(③)에서 직접 계산해 전달한다(Chroma 기본 임베더 미사용).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np

# Chroma 메타데이터로 허용되는 스칼라 타입
_SCALAR = (str, int, float, bool)


def _sanitize_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Chroma 는 str/int/float/bool 스칼라만 허용 → 그 외 값은 문자열화/제거."""
    clean: dict[str, Any] = {}
    for key, value in meta.items():
        if value is None:
            continue
        clean[key] = value if isinstance(value, _SCALAR) else str(value)
    return clean


class ChromaVectorStore:
    def __init__(self, persist_dir: str, collection_name: str) -> None:
        import chromadb

        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(
        self,
        ids: list[str],
        embeddings: np.ndarray | list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if len(ids) == 0:
            return
        if isinstance(embeddings, np.ndarray):
            embeddings = embeddings.tolist()
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=[_sanitize_meta(m) for m in metadatas],
        )

    def query(
        self,
        query_embedding: np.ndarray | list[float],
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """코사인 기반 의미 탐색 (⑪ 에서 본격 사용)."""
        if isinstance(query_embedding, np.ndarray):
            query_embedding = query_embedding.tolist()
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
        )

    def delete_by_document(self, document_id: int) -> None:
        self.collection.delete(where={"document_id": document_id})

    def count(self) -> int:
        return self.collection.count()


@lru_cache
def get_vector_store() -> ChromaVectorStore:
    from ..config import get_settings

    settings = get_settings()
    return ChromaVectorStore(
        persist_dir=settings.chroma_persist_dir,
        collection_name=settings.chroma_collection,
    )
