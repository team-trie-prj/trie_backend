"""문서 통신 API — 멀티 업로드·조회·삭제 (F2) + 메타 동기화 (F7). 김예담.

프로덕션 문서 통신 계층 (루트 `/documents`).
vikira 파이프라인 검증용 하니스(`/api/v1/documents/ingest`)와는 별개이며,
업로드 시 vikira `ingest_file` 서비스를 in-process 호출한다.
응답은 공통 envelope 로 감싼다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..response import ApiResponse, ok
from ..schemas import DocumentOut, MultiUploadResponse
from ..security.deps import get_current_user_id
from ..services import document_service

router = APIRouter(prefix="/documents", tags=["documents(통신)"])


@router.post("", response_model=ApiResponse[MultiUploadResponse])
def upload_documents(
    files: list[UploadFile] = File(...),
    domain: str = Form("etc"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """비정형 문서(PDF/DOCX) 멀티 업로드 → 검증·저장·수집 + 업로더 메타 동기화(F7)."""
    return ok(document_service.upload_many(db, files, domain, user_id), message="업로드 완료")


@router.get("", response_model=ApiResponse[list[DocumentOut]])
def list_documents(domain: str | None = None, db: Session = Depends(get_db)) -> dict:
    """문서 목록(최신순, domain 필터 선택)."""
    return ok(document_service.list_documents(db, domain))


@router.get("/{document_id}", response_model=ApiResponse[DocumentOut])
def get_document(document_id: int, db: Session = Depends(get_db)) -> dict:
    """문서 단건 조회."""
    return ok(document_service.get_document(db, document_id))


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    _uid: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """문서 + ChromaDB 벡터 + 저장 파일 동기 삭제."""
    document_service.delete_document(db, document_id)
    return ok(data={"document_id": document_id}, message="deleted")
