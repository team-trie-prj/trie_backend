"""② 시맨틱 청킹(Semantic Chunking) 및 오버랩 적용  (FNC-DAT-02)

- SemanticChunker : 문장 임베딩 간 코사인 거리로 '의미 경계'를 찾아 분할.
    · 인접 문장 임베딩 거리(1 - cosine)가 상위 percentile 을 넘으면 주제 전환으로 보고 끊음
    · max_chars 초과 시 강제 분할, min_chars 미만이면 경계여도 유지(과분할 방지)
    · 청크 간 문장 단위 오버랩으로 문맥 단절 완화
- RecursiveChunker : 임베딩 없이 문단/문장 기준으로 크기 맞춰 자르는 폴백.

문장 분리는 kiwipiepy(있으면) → 정규식 순으로 폴백한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from .embedding import Embedder

# 한국어/영문 문장 종결 경계 (마침표류 뒤 공백 또는 개행)
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?。？！])\s+|\n+")


@dataclass
class Chunk:
    index: int
    text: str
    char_count: int
    token_estimate: int
    meta: dict = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """토크나이저 없이 대략적 토큰 수 추정 (한/영 혼합 ~2.5자/토큰)."""
    return max(1, round(len(text) / 2.5))


_kiwi = None
_kiwi_failed = False


def split_sentences(text: str) -> list[str]:
    """문장 분리 — kiwipiepy 우선, 실패 시 정규식."""
    global _kiwi, _kiwi_failed
    text = text.strip()
    if not text:
        return []

    if not _kiwi_failed:
        try:
            if _kiwi is None:
                from kiwipiepy import Kiwi

                _kiwi = Kiwi()
            sents = [s.text.strip() for s in _kiwi.split_into_sents(text)]
            return [s for s in sents if s]
        except Exception:
            _kiwi_failed = True  # 이후 정규식 폴백 고정

    return [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]


def _hard_split(sentence: str, max_chars: int) -> list[str]:
    """max_chars 를 크게 초과하는 단일 문장을 문자 단위로 강제 분할."""
    if len(sentence) <= max_chars:
        return [sentence]
    return [sentence[i : i + max_chars] for i in range(0, len(sentence), max_chars)]


class SemanticChunker:
    def __init__(
        self,
        embedder: Embedder,
        max_chars: int = 1000,
        min_chars: int = 200,
        overlap_sentences: int = 1,
        breakpoint_percentile: int = 90,
    ) -> None:
        self.embedder = embedder
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.overlap_sentences = max(0, overlap_sentences)
        self.breakpoint_percentile = breakpoint_percentile

    def chunk(self, text: str, base_meta: dict | None = None) -> list[Chunk]:
        base_meta = base_meta or {}

        raw_sents = split_sentences(text)
        # 과대 문장 강제 분할
        sents: list[str] = []
        for s in raw_sents:
            sents.extend(_hard_split(s, self.max_chars))

        if not sents:
            return []
        if len(sents) == 1:
            return [self._make_chunk(0, [sents[0]], base_meta)]

        # 문장 임베딩 → 인접 거리 계산
        embeddings = self.embedder.embed_texts(sents)
        distances = self._consecutive_distances(embeddings)
        threshold = float(np.percentile(distances, self.breakpoint_percentile))

        # 그룹핑
        groups: list[list[int]] = []
        current: list[int] = [0]
        current_len = len(sents[0])
        for i in range(1, len(sents)):
            gap = distances[i - 1]
            projected = current_len + 1 + len(sents[i])
            semantic_break = gap >= threshold and current_len >= self.min_chars
            size_break = projected > self.max_chars
            if semantic_break or size_break:
                groups.append(current)
                current = [i]
                current_len = len(sents[i])
            else:
                current.append(i)
                current_len = projected
        groups.append(current)

        # 오버랩 적용 후 청크 생성
        chunks: list[Chunk] = []
        for gi, group in enumerate(groups):
            idxs = list(group)
            if gi > 0 and self.overlap_sentences > 0:
                overlap = groups[gi - 1][-self.overlap_sentences :]
                idxs = overlap + idxs
            chunk_sents = [sents[j] for j in idxs]
            chunks.append(self._make_chunk(gi, chunk_sents, base_meta))
        return chunks

    @staticmethod
    def _consecutive_distances(embeddings: np.ndarray) -> np.ndarray:
        # 정규화 임베딩 가정 → 코사인 유사도 = 내적
        sims = np.sum(embeddings[:-1] * embeddings[1:], axis=1)
        sims = np.clip(sims, -1.0, 1.0)
        return 1.0 - sims

    def _make_chunk(self, index: int, sentences: list[str], base_meta: dict) -> Chunk:
        text = " ".join(sentences).strip()
        return Chunk(
            index=index,
            text=text,
            char_count=len(text),
            token_estimate=estimate_tokens(text),
            meta={**base_meta, "n_sentences": len(sentences), "strategy": "semantic"},
        )


class RecursiveChunker:
    """임베딩 없이 문장을 크기 기준으로 묶는 폴백 청커."""

    def __init__(
        self,
        max_chars: int = 1000,
        overlap_sentences: int = 1,
        **_ignored,
    ) -> None:
        self.max_chars = max_chars
        self.overlap_sentences = max(0, overlap_sentences)

    def chunk(self, text: str, base_meta: dict | None = None) -> list[Chunk]:
        base_meta = base_meta or {}
        raw_sents = split_sentences(text)
        sents: list[str] = []
        for s in raw_sents:
            sents.extend(_hard_split(s, self.max_chars))
        if not sents:
            return []

        groups: list[list[int]] = []
        current: list[int] = []
        current_len = 0
        for i, s in enumerate(sents):
            projected = current_len + (1 if current else 0) + len(s)
            if current and projected > self.max_chars:
                groups.append(current)
                current = [i]
                current_len = len(s)
            else:
                current.append(i)
                current_len = projected
        if current:
            groups.append(current)

        chunks: list[Chunk] = []
        for gi, group in enumerate(groups):
            idxs = list(group)
            if gi > 0 and self.overlap_sentences > 0:
                idxs = groups[gi - 1][-self.overlap_sentences :] + idxs
            text_c = " ".join(sents[j] for j in idxs).strip()
            chunks.append(
                Chunk(
                    index=gi,
                    text=text_c,
                    char_count=len(text_c),
                    token_estimate=estimate_tokens(text_c),
                    meta={**base_meta, "n_sentences": len(idxs), "strategy": "recursive"},
                )
            )
        return chunks


def build_chunker(settings, embedder: Embedder | None = None):
    """설정 기반 청커 팩토리."""
    if settings.chunk_strategy == "semantic" and embedder is not None:
        return SemanticChunker(
            embedder=embedder,
            max_chars=settings.chunk_max_chars,
            min_chars=settings.chunk_min_chars,
            overlap_sentences=settings.chunk_overlap_sentences,
            breakpoint_percentile=settings.semantic_breakpoint_percentile,
        )
    return RecursiveChunker(
        max_chars=settings.chunk_max_chars,
        overlap_sentences=settings.chunk_overlap_sentences,
    )
