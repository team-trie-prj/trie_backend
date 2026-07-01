"""수집 파이프라인 단위 테스트 (torch/모델 불필요 — HashingEmbedder 사용)."""

from __future__ import annotations

import numpy as np

from app.pipeline.chunking import RecursiveChunker, SemanticChunker, split_sentences
from app.pipeline.embedding import HashingEmbedder
from app.pipeline.parsing import clean_text


# --------------------------- ① 파싱/노이즈 필터링 ---------------------------
def test_clean_text_removes_repeated_header_footer():
    pages = [f"보고서 머리말\n본문 내용 {i}\n{i}" for i in range(1, 6)]
    out = clean_text(pages)
    # 5개 페이지 공통 머리말은 제거되어야 함
    assert "보고서 머리말" not in out
    # 페이지 번호 단독 라인도 제거
    assert "\n1\n" not in out
    assert "본문 내용 3" in out


def test_clean_text_normalizes_whitespace():
    pages = ["줄1   에   공백\n\n\n\n줄2"]
    out = clean_text(pages)
    assert "   " not in out
    assert "\n\n\n" not in out


def test_clean_text_drops_symbol_only_lines():
    pages = ["의미 있는 문장이다.\n------\n다음 문장이다."]
    out = clean_text(pages)
    assert "------" not in out
    assert "의미 있는 문장이다." in out


# --------------------------- 문장 분리 ---------------------------
def test_split_sentences_basic():
    text = "첫 번째 문장이다. 두 번째 문장이다! 세 번째는 질문인가?"
    sents = split_sentences(text)
    assert len(sents) >= 3


# --------------------------- ③ 임베딩 (Hashing) ---------------------------
def test_hashing_embedder_is_normalized_and_deterministic():
    emb = HashingEmbedder(dimension=64)
    v1 = emb.embed_texts(["포트홀 보수 절차"])
    v2 = emb.embed_texts(["포트홀 보수 절차"])
    assert v1.shape == (1, 64)
    np.testing.assert_allclose(v1, v2)  # 결정적
    assert abs(np.linalg.norm(v1[0]) - 1.0) < 1e-5  # 정규화


def test_hashing_embedder_similarity_orders_related_higher():
    emb = HashingEmbedder(dimension=512)
    base = emb.embed_query("도로 포트홀 보수 공사")
    related = emb.embed_query("포트홀 보수 공사 절차")
    unrelated = emb.embed_query("점심 메뉴 추천 파스타")
    assert float(base @ related) > float(base @ unrelated)


# --------------------------- ② 시맨틱 청킹 + 오버랩 ---------------------------
def _long_text() -> str:
    road = "도로 포트홀 보수는 아스팔트 절단 후 채움재를 다진다. " * 6
    safety = "산업 현장에서는 안전모와 보호구 착용이 필수적이다. " * 6
    return road + safety


def test_semantic_chunker_produces_multiple_chunks_with_overlap():
    emb = HashingEmbedder(dimension=256)
    chunker = SemanticChunker(
        embedder=emb, max_chars=200, min_chars=50, overlap_sentences=1, breakpoint_percentile=80
    )
    chunks = chunker.chunk(_long_text(), base_meta={"document_id": 1})
    assert len(chunks) >= 2
    # 크기 상한 근처 준수 (오버랩으로 약간 초과 가능 → 여유 배수)
    assert all(c.char_count <= 200 * 2 for c in chunks)
    # 인덱스 연속성
    assert [c.index for c in chunks] == list(range(len(chunks)))
    # 메타 전파
    assert chunks[0].meta["document_id"] == 1


def test_recursive_chunker_respects_max_chars():
    chunker = RecursiveChunker(max_chars=120, overlap_sentences=0)
    chunks = chunker.chunk(_long_text())
    assert len(chunks) >= 2
    assert all(c.char_count <= 120 * 2 for c in chunks)


def test_chunker_handles_empty_and_single_sentence():
    emb = HashingEmbedder(dimension=32)
    chunker = SemanticChunker(embedder=emb)
    assert chunker.chunk("") == []
    single = chunker.chunk("한 문장뿐이다.")
    assert len(single) == 1
