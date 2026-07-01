"""GeneratedReport — AI 생성 실무 보고서 초안.

phase ⑤(검색 데이터 + 서식 결합 메타 프롬프팅)에서 채운다. 지금은 스키마 골격만 정의.
세션 단위 식별자(session_id)로 '동일 결과 반복 캐시' 문제를 방지한다.
"""

from __future__ import annotations

import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from ..database import Base


class GeneratedReport(Base):
    __tablename__ = "generated_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    domain: Mapped[str] = mapped_column(String(16), default="etc")
    report_type: Mapped[str] = mapped_column(String(32), default="draft")

    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # Markdown

    # 입력 질의 / 참조 근거 / 사용 데이터 출처 메타데이터
    sources: Mapped[list] = mapped_column(JSON, default=list)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow
    )
