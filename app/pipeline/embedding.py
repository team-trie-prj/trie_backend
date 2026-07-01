"""③ BGE-m3 경량 모델 기반 벡터 임베딩 생성  (FNC-DAT-02 / 로컬·무료)

- BGEM3Embedder : sentence-transformers 로 BAAI/bge-m3 dense 임베딩(1024d, cosine 정규화).
  모델(~2.3GB)은 최초 사용 시 지연 로딩된다.
- HashingEmbedder : torch/모델 없이 동작하는 zero-dependency 대체 임베더(개발/테스트/오프라인용).
  실제 의미 품질은 낮지만 파이프라인 전 구간을 비용 0으로 검증할 수 있다.

두 구현 모두 Embedder 프로토콜(embed_texts / embed_query / dimension)을 만족한다.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class Embedder(Protocol):
    dimension: int

    def embed_texts(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class BGEM3Embedder:
    """BAAI/bge-m3 dense 임베딩 (지연 로딩 싱글턴)."""

    dimension = 1024

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str = "cpu",
        batch_size: int = 16,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        self._ensure_model()
        vectors = self._model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,  # cosine 유사도용 정규화
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_texts([text])[0]


class HashingEmbedder:
    """torch 없이 동작하는 결정적 해싱 임베더 (개발/테스트 대체용)."""

    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension
        self._token_re = re.compile(r"[0-9A-Za-z가-힣]+")

    def _embed_one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dimension, dtype=np.float32)
        tokens = self._token_re.findall(text.lower())
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dimension] += 1.0
        return vec

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        mat = np.vstack([self._embed_one(t) for t in texts])
        return _l2_normalize(mat).astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_texts([text])[0]


@lru_cache
def get_embedder() -> Embedder:
    """설정에 따른 임베더 싱글턴."""
    from ..config import get_settings

    settings = get_settings()
    if settings.embedding_backend == "hashing":
        return HashingEmbedder()
    return BGEM3Embedder(
        model_name=settings.embedding_model_name,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
    )
