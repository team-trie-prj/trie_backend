"""phase ④ 검색 실행 단위 테스트 (모델 불필요 — in-memory SQLite + rerank=none)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import DocumentChunk, KnowledgeDocument
from app.search import keyword_search, rerank, truncate_to_budget
from app.search.schemas import SearchHit
from app.services.search_service import execute_search


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    doc = KnowledgeDocument(title="도로 지침", doc_type="pdf", domain="road", status="indexed")
    session.add(doc)
    session.flush()
    rows = [
        ("포트홀 보수는 아스팔트를 절단한 뒤 채움재를 다져 시공한다.", 0),
        ("안전모 착용은 산업안전 관리의 기본 수칙이다.", 1),
        ("도로 균열 보수 절차와 관련 규정을 상세히 설명한다.", 2),
    ]
    for text, idx in rows:
        session.add(
            DocumentChunk(
                document_id=doc.id, chunk_index=idx, text=text,
                char_count=len(text), token_estimate=len(text) // 2,
                vector_id=f"doc{doc.id}_chunk{idx}", meta={"domain": "road", "document_id": doc.id},
            )
        )
    session.commit()
    yield session
    session.close()


def test_keyword_search_ranks_multi_match_first(db):
    hits = keyword_search(["포트홀", "보수"], domain="road", db=db, limit=10)
    assert hits
    assert "포트홀" in hits[0].text  # 포트홀+보수 둘 다 매칭된 청크가 최상위


def test_keyword_search_regex_precision(db):
    hits = keyword_search(["보수"], db=db, regex=r"균열\s*보수")
    assert len(hits) == 1
    assert "균열" in hits[0].text


def test_keyword_search_domain_filter(db):
    assert keyword_search(["포트홀"], domain="safety", db=db) == []


def test_execute_search_keyword_route(db):
    res = execute_search(
        "포트홀 보수", route="keyword", keywords=["포트홀", "보수"],
        domain="road", db=db, rerank_backend="none",
    )
    assert res.route == "keyword"
    assert res.hits
    assert res.used_tokens > 0


def test_execute_search_clarify_and_public_api_return_notes():
    r1 = execute_search("모호", route="clarify")
    assert r1.hits == [] and r1.note
    r2 = execute_search("통계", route="public_api")
    assert r2.hits == [] and r2.note


def test_truncate_to_budget_stops_at_limit():
    hits = [SearchHit("keyword", 1, i, "가" * 100, 1.0) for i in range(5)]  # ~40 tok each
    selected, used, truncated = truncate_to_budget(hits, max_tokens=90)
    assert truncated is True
    assert len(selected) == 2  # 40 + 40 <= 90, 세 번째(120)에서 중단
    assert used <= 90


def test_rerank_none_sorts_by_existing_score():
    hits = [SearchHit("keyword", 1, 0, "a", 0.2), SearchHit("keyword", 1, 1, "b", 0.9)]
    out = rerank("q", hits, backend="none")
    assert out[0].score == 0.9


def test_dedup_keeps_higher_score():
    from app.services.search_service import _dedup

    h1 = SearchHit("vector", 1, 0, "동일 청크", 0.5, vector_id="doc1_chunk0")
    h2 = SearchHit("keyword", 1, 0, "동일 청크", 0.9, vector_id="doc1_chunk0")
    out = _dedup([h1, h2])
    assert len(out) == 1
    assert out[0].score == 0.9
