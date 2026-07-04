"""보안 — 프롬프트 인젝션 사전 검사 스키마 (김예담)."""

from __future__ import annotations

from pydantic import BaseModel


class PromptCheckRequest(BaseModel):
    text: str


class PromptScanOut(BaseModel):
    flagged: bool
    matches: list[str]
