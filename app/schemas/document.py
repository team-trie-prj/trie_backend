"""문서/수집 관련 응답 스키마."""

from __future__ import annotations

import datetime

from pydantic import BaseModel


class ChunkPreview(BaseModel):
    index: int
    char_count: int
    token_estimate: int
    text: str


class IngestResponse(BaseModel):
    document_id: int
    title: str
    doc_type: str
    domain: str
    status: str
    char_count: int
    chunk_count: int
    elapsed_sec: float
    chunk_preview: list[ChunkPreview]


class DocumentOut(BaseModel):
    id: int
    title: str
    doc_type: str
    domain: str
    status: str
    char_count: int
    chunk_count: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True


# --- F2 멀티 업로드 (김예담) ---
class UploadedDocument(BaseModel):
    document_id: int
    title: str
    doc_type: str
    domain: str
    status: str
    chunk_count: int
    uploaded_by: int | None = None
    original_filename: str | None = None


class UploadFailure(BaseModel):
    filename: str | None = None
    detail: str


class MultiUploadResponse(BaseModel):
    items: list[UploadedDocument]
    failed: list[UploadFailure]
