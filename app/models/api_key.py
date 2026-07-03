"""ApiKey — 외부 API 키의 암호화 저장 (F5, 김예담).

`secret_encrypted` 에는 Fernet 로 암호화된 값만 저장한다(평문 저장 금지).
"""

from __future__ import annotations

import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ..utils import utcnow


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    secret_encrypted: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=utcnow, onupdate=utcnow)
