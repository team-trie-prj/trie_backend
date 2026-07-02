"""PublicApiCatalog — 공공데이터 오픈 API 카탈로그 메타 (F6, 김예담).

`params_spec` 예:
    [{"name": "sidoName", "type": "str", "required": true, "default": null, "map_from": "region"}]

- `api_key_name`: F5 ApiKey.name 참조 — F10 호출 시 복호화하여 `api_key_param`(기본 serviceKey)으로 주입.
"""

from __future__ import annotations

import datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class PublicApiCatalog(Base):
    __tablename__ = "public_api_catalogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    domain: Mapped[str] = mapped_column(String(16), default="etc", index=True)
    endpoint: Mapped[str] = mapped_column(Text)
    http_method: Mapped[str] = mapped_column(String(8), default="GET")
    params_spec: Mapped[list] = mapped_column(JSON, default=list)
    api_key_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_key_param: Mapped[str] = mapped_column(String(64), default="serviceKey")
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
