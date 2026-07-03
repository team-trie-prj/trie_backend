"""문서 통신 서비스 — 멀티 업로드·삭제 (F2) + 메타데이터 동기화 (F7). 김예담.

- 업로드: 파일 저장 → vikira `ingest_file` 호출 → 업로더/원본파일명/업로드시각 메타를 RDBMS 동기화.
- 삭제: 저장 파일 + ChromaDB 벡터(`delete_by_document`) + RDBMS 행(청크 cascade) 제거.
"""

from __future__ import annotations

import datetime
import os
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import KnowledgeDocument
from ..pipeline.parsing import SUPPORTED_EXTS
from ..services.ingestion import ingest_file
from ..vectorstore import get_vector_store


def _save_upload(file: UploadFile, ext: str) -> str:
    settings = get_settings()
    saved_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}{ext}")
    with open(saved_path, "wb") as f:
        f.write(file.file.read())
    return saved_path


def upload_one(db: Session, file: UploadFile, domain: str, uploaded_by: int) -> dict:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(
            status_code=422,
            detail=f"지원하지 않는 형식: {ext or '(없음)'} / 지원: {sorted(SUPPORTED_EXTS)}",
        )

    saved_path = _save_upload(file, ext)
    title = os.path.splitext(file.filename or "")[0]
    result = ingest_file(path=saved_path, db=db, domain=domain, title=title)

    # F7: 업로더/원본파일명/업로드시각 메타 RDBMS 동기화
    doc = db.get(KnowledgeDocument, result.document_id)
    if doc is not None:
        meta = dict(doc.meta or {})
        meta.update(
            {
                "uploaded_by": uploaded_by,
                "original_filename": file.filename,
                "uploaded_at": datetime.datetime.utcnow().isoformat(),
            }
        )
        doc.meta = meta
        db.commit()

    return {
        "document_id": result.document_id,
        "title": result.title,
        "doc_type": result.doc_type,
        "domain": result.domain,
        "status": result.status,
        "chunk_count": result.chunk_count,
        "uploaded_by": uploaded_by,
        "original_filename": file.filename,
    }


def upload_many(db: Session, files: list[UploadFile], domain: str, uploaded_by: int) -> dict:
    items: list[dict] = []
    failed: list[dict] = []
    for f in files:
        try:
            items.append(upload_one(db, f, domain, uploaded_by))
        except HTTPException as exc:
            failed.append({"filename": f.filename, "detail": str(exc.detail)})
        except Exception as exc:  # noqa: BLE001
            failed.append({"filename": f.filename, "detail": f"수집 실패: {exc}"})
    return {"items": items, "failed": failed}


def list_documents(db: Session, domain: str | None = None) -> list[KnowledgeDocument]:
    stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc())
    if domain:
        stmt = stmt.where(KnowledgeDocument.domain == domain)
    return list(db.scalars(stmt).all())


def get_document(db: Session, document_id: int) -> KnowledgeDocument:
    doc = db.get(KnowledgeDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return doc


def delete_document(db: Session, document_id: int) -> None:
    doc = get_document(db, document_id)

    # ChromaDB 벡터 제거 (best-effort)
    try:
        get_vector_store().delete_by_document(document_id)
    except Exception:  # noqa: BLE001
        pass

    # 저장 파일 제거
    if doc.source_path and os.path.exists(doc.source_path):
        try:
            os.remove(doc.source_path)
        except OSError:
            pass

    db.delete(doc)  # DocumentChunk 는 cascade 삭제
    db.commit()
