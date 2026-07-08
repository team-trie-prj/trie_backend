"""공공데이터 카탈로그/호출 스키마 (F6·F9·F10)."""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ParamSpec(BaseModel):
    """카탈로그 파라미터 명세 — F9 동적 매핑의 기준."""

    name: str
    type: str = "str"  # str | int | float | bool
    required: bool = False
    default: Any = None
    map_from: str | None = None  # 질의 엔티티 별칭 (예: region → sidoName)


class CatalogCreate(BaseModel):
    name: str
    endpoint: str
    provider: str | None = None
    domain: str = "etc"
    http_method: str = "GET"
    params_spec: list[ParamSpec] = []
    api_key_name: str | None = None  # F5 ApiKey.name 참조
    api_key_param: str = "serviceKey"
    description: str | None = None


class CatalogOut(CatalogCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime


class FetchRequest(BaseModel):
    """F9 입력 — 질의에서 추출된 엔티티(파라미터 원료)."""

    entities: dict[str, Any] = {}


class FetchResponse(BaseModel):
    """F10 출력 — 실시간 호출 결과 (서비스 키는 마스킹).

    source: live(실시간) | local_fallback(장애/타임아웃 시 마지막 성공 스냅샷 우회)
    """

    catalog_id: int
    api_name: str
    provider: str | None = None
    endpoint: str
    assembled_params: dict[str, Any]
    status_code: int
    items: list | None = None
    data: Any = None  # items 추출 실패 시 원본(요약)
    elapsed_sec: float
    source: str = "live"
    cached_at: datetime.datetime | None = None  # source=local_fallback 일 때 스냅샷 시각


class SessionUUIDOut(BaseModel):
    """F8 — 매 쿼리 난수 세션 UUID."""

    session_uuid: str
    issued_at: datetime.datetime
