"""작업 12 — RDBMS 기반 사내 문서 키워드/정규식 정밀 탐색.

DocumentChunk.text 를 SQL ILIKE(키워드 OR) 로 1차 필터하고, 정규식이 주어지면
후보 행에 대해 Python re 로 2차 정밀 필터한다. (SQLite/PostgreSQL 공통 동작)
"""

from __future__ import annotations

import re

from sqlalchemy import or_, select

from ..database import SessionLocal
from ..models import DocumentChunk, KnowledgeDocument
from .schemas import SearchHit


def _kw_score(text: str, keywords: list[str]) -> float:
    low = text.lower()
    matched = 0
    occurrences = 0
    for kw in keywords:
        kw = kw.lower().strip()
        if not kw:
            continue
        cnt = low.count(kw)
        if cnt:
            matched += 1
            occurrences += cnt
    return matched + 0.1 * occurrences


def keyword_search(
    keywords: list[str],
    domain: str | None = None,
    db=None,
    limit: int = 20,
    regex: str | None = None,
) -> list[SearchHit]:
    keywords = [k for k in (keywords or []) if k and k.strip()]
    if not keywords and not regex:
        return []

    close = False
    if db is None:
        db = SessionLocal()
        close = True
    try:
        stmt = select(DocumentChunk)
        if keywords:
            stmt = stmt.where(or_(*[DocumentChunk.text.ilike(f"%{kw}%") for kw in keywords]))
        if domain and domain != "etc":
            stmt = stmt.join(KnowledgeDocument).where(KnowledgeDocument.domain == domain)

        # 정규식이 있으면 후보를 넉넉히 뽑아 Python 에서 정밀 필터
        fetch = limit * 3 if regex else limit
        rows = db.scalars(stmt.limit(fetch)).all()

        pattern = re.compile(regex) if regex else None
        hits: list[SearchHit] = []
        for row in rows:
            if pattern and not pattern.search(row.text):
                continue
            hits.append(
                SearchHit(
                    source="keyword",
                    document_id=row.document_id,
                    chunk_index=row.chunk_index,
                    text=row.text,
                    score=_kw_score(row.text, keywords) if keywords else 1.0,
                    domain=str((row.meta or {}).get("domain", "etc")),
                    vector_id=row.vector_id,
                    meta=row.meta or {},
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]
    finally:
        if close:
            db.close()
