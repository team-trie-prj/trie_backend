"""PublicFetchCache — 공공 API 응답 로컬 캐시 (F10 장애/타임아웃 로컬 우회용).

성공 응답을 (catalog_id, params_hash) 단위로 보관하고,
외부 API 장애/타임아웃 시 마지막 성공 스냅샷으로 우회(Fallback)한다.
"""

from __future__ import annotations

import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from ..database import Base
from ..utils import utcnow


class PublicFetchCache(Base):
    __tablename__ = "public_fetch_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int] = mapped_column(Integer, index=True)
    params_hash: Mapped[str] = mapped_column(String(32), index=True)
    response: Mapped[dict] = mapped_column(JSON, default=dict)  # FetchResponse 스냅샷
    fetched_at: Mapped[datetime.datetime] = mapped_column(default=utcnow)
