"""API Key 요청/응답 스키마 (F5). 평문은 응답에 포함하지 않는다."""

from __future__ import annotations

import datetime

from pydantic import BaseModel


class ApiKeyCreate(BaseModel):
    name: str
    secret: str
    provider: str | None = None
    description: str | None = None


class ApiKeyMasked(BaseModel):
    name: str
    provider: str | None = None
    secret_preview: str
    description: str | None = None
    updated_at: datetime.datetime
