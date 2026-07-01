"""수집 파이프라인 오케스트레이션.

parse(①) → chunk(②) → embed(③) → index(⑤) → RDBMS 메타 적재

이 서비스는 vikira 파이프라인의 '재사용 코어'다. 프로덕션의 멀티 업로드 통신 로직
(FNC-DAT-01, 김예담)이 파일을 저장한 뒤 이 서비스를 호출하는 구조를 가정한다.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import DocStatus, DocumentChunk, KnowledgeDocument
from ..pipeline.chunking import build_chunker
from ..pipeline.embedding import get_embedder
from ..pipeline.parsing import parse_document
from ..vectorstore import get_vector_store


@dataclass
class IngestionResult:
    document_id: int
    title: str
    doc_type: str
    domain: str
    status: str
    char_count: int
    chunk_count: int
    elapsed_sec: float
    chunk_preview: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def ingest_file(
    path: str,
    db: Session,
    domain: str = "etc",
    title: str | None = None,
    preview: int = 3,
) -> IngestionResult:
    settings = get_settings()
    started = time.perf_counter()

    document = KnowledgeDocument(
        title=title or "",
        source_path=path,
        doc_type="",
        domain=domain,
        status=DocStatus.PENDING.value,
    )
    db.add(document)
    db.flush()  # document.id 확보

    try:
        # ① 파싱 + 노이즈 필터링
        parsed = parse_document(path)
        document.title = title or parsed.title
        document.doc_type = parsed.doc_type
        document.raw_text = parsed.text
        document.char_count = parsed.char_count
        document.meta = {**parsed.meta, "page_count": parsed.page_count}
        document.status = DocStatus.PARSED.value
        db.flush()

        # ② 시맨틱 청킹 + 오버랩
        embedder = get_embedder()
        chunker = build_chunker(settings, embedder)
        base_meta = {"document_id": document.id, "domain": domain, "title": document.title}
        chunks = chunker.chunk(parsed.text, base_meta=base_meta)
        document.status = DocStatus.CHUNKED.value

        if not chunks:
            document.chunk_count = 0
            document.status = DocStatus.INDEXED.value
            db.commit()
            return _build_result(document, [], started)

        # ③ BGE-m3 임베딩
        embeddings = embedder.embed_texts([c.text for c in chunks])

        # RDBMS 청크 행 생성 + ⑤ ChromaDB 적재 준비
        ids: list[str] = []
        documents_text: list[str] = []
        metadatas: list[dict] = []
        chunk_rows: list[DocumentChunk] = []

        for chunk in chunks:
            vector_id = f"doc{document.id}_chunk{chunk.index}"
            row = DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.index,
                text=chunk.text,
                char_count=chunk.char_count,
                token_estimate=chunk.token_estimate,
                vector_id=vector_id,
                meta=chunk.meta,
            )
            chunk_rows.append(row)
            ids.append(vector_id)
            documents_text.append(chunk.text)
            metadatas.append(
                {
                    "document_id": document.id,
                    "chunk_index": chunk.index,
                    "domain": domain,
                    "title": document.title,
                    "source_path": path,
                }
            )

        db.add_all(chunk_rows)

        # ⑤ ChromaDB 인덱싱
        store = get_vector_store()
        store.add_chunks(ids, embeddings, documents_text, metadatas)

        document.chunk_count = len(chunks)
        document.status = DocStatus.INDEXED.value
        db.commit()

        return _build_result(document, chunks, started, preview)

    except Exception as exc:
        db.rollback()
        # rollback 으로 detached 된 객체 대신, 실패 레코드를 새로 기록
        failed = KnowledgeDocument(
            title=title or "",
            source_path=path,
            doc_type="",
            domain=domain,
            status=DocStatus.FAILED.value,
            meta={"error": str(exc)[:500]},
        )
        db.add(failed)
        db.commit()
        raise


def _build_result(document, chunks, started, preview: int = 3) -> IngestionResult:
    return IngestionResult(
        document_id=document.id,
        title=document.title,
        doc_type=document.doc_type,
        domain=document.domain,
        status=document.status,
        char_count=document.char_count,
        chunk_count=document.chunk_count,
        elapsed_sec=round(time.perf_counter() - started, 3),
        chunk_preview=[
            {
                "index": c.index,
                "char_count": c.char_count,
                "token_estimate": c.token_estimate,
                "text": c.text[:160] + ("…" if len(c.text) > 160 else ""),
            }
            for c in chunks[:preview]
        ],
    )
