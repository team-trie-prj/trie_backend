"""KnowledgeDocument / DocumentChunk — 사내 문서 원본 및 청크 저장.

수집 파이프라인(vikira ①→②→③→⑤)의 산출물이 여기에 적재된다.
  - 원본 텍스트 / 문서 메타데이터
  - 청크 단위 분할 텍스트 + 토큰 추정 + Vector DB 색인 id(vector_id)
"""

from __future__ import annotations

import datetime
import enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from ..database import Base


class Domain(str, enum.Enum):
    """명세서 3개 도메인 + 기타 (이후 '도메인 자율 태깅' 작업의 라벨)."""

    ROAD = "road"  # RoadFacilityManagement
    SAFETY = "safety"  # IndustrialSafetyManagement
    TRAFFIC = "traffic"  # TrafficManagement
    ETC = "etc"


class DocStatus(str, enum.Enum):
    """수집 파이프라인 진행 상태."""

    PENDING = "pending"
    PARSED = "parsed"
    CHUNKED = "chunked"
    INDEXED = "indexed"
    FAILED = "failed"


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    source_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(16))  # pdf / docx / txt
    domain: Mapped[str] = mapped_column(String(16), default=Domain.ETC.value, index=True)
    status: Mapped[str] = mapped_column(String(16), default=DocStatus.PENDING.value)

    char_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)

    # 파싱 원문 (검색 실행 단계의 RDBMS 키워드/정규식 정밀 탐색에 사용)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)

    # ChromaDB 내 벡터 id (⑤ 적재 시 기록)
    vector_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
