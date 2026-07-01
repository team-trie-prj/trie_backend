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
