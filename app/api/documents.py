"""문서 수집/조회 API.

주의: 프로덕션 멀티 업로드 통신 로직(FNC-DAT-01)은 김예담 담당.
여기의 /ingest 는 vikira 파이프라인을 단독 구동/검증하기 위한 얇은 하니스다.
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import KnowledgeDocument
from ..pipeline.parsing import SUPPORTED_EXTS
from ..schemas import DocumentOut, IngestResponse, MultiUploadResponse
from ..security.deps import get_current_user_id
from ..services import document_service
from ..services.ingestion import ingest_file

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    domain: str = Form("etc"),
    db: Session = Depends(get_db),
) -> IngestResponse:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(
            status_code=415,
            detail=f"지원하지 않는 형식: {ext or '(없음)'} / 지원: {sorted(SUPPORTED_EXTS)}",
        )

    settings = get_settings()
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(settings.upload_dir, saved_name)
    contents = await file.read()
    with open(saved_path, "wb") as f:
        f.write(contents)

    try:
        result = ingest_file(
            path=saved_path,
            db=db,
            domain=domain,
            title=os.path.splitext(file.filename or saved_name)[0],
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"수집 실패: {exc}") from exc

    return IngestResponse(**result.as_dict())


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[KnowledgeDocument]:
    stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc())
    return list(db.scalars(stmt).all())


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db)) -> KnowledgeDocument:
    doc = db.get(KnowledgeDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return doc


# ===== 김예담: 프로덕션 멀티 업로드(F2) + 삭제(F2) + 메타 동기화(F7) =====


@router.post("", response_model=MultiUploadResponse)
def upload_documents(
    files: list[UploadFile] = File(...),
    domain: str = Form("etc"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MultiUploadResponse:
    """비정형 문서(PDF/DOCX) 멀티 업로드 → 검증·저장·수집 + 업로더 메타 동기화."""
    return document_service.upload_many(db, files, domain, user_id)


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    _uid: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """문서 + 벡터 + 저장 파일 동기 삭제."""
    document_service.delete_document(db, document_id)
    return {"detail": "deleted", "document_id": document_id}
