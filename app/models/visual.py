"""VisualResource — 현장 점검 이미지 + VLM 분석 맥락.

phase ②(VLM 이미지 시각적 맥락 추출)에서 채운다. 지금은 스키마 골격만 정의.
"""

from __future__ import annotations

import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from ..database import Base


class VisualResource(Base):
    __tablename__ = "visual_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_path: Mapped[str] = mapped_column(String(1024))
    domain: Mapped[str] = mapped_column(String(16), default="etc", index=True)

    # VLM 분석 결과: 이미지 맥락 텍스트 / 라벨 / 상황 묘사 / 추정 원인
    vlm_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    labels: Mapped[list] = mapped_column(JSON, default=list)

    # 촬영 시각 / 위치 / 현장 구분 등 연계 메타데이터
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow
    )
