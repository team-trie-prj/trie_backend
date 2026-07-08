"""공공데이터 서비스 (김예담).

- F6: 오픈 API 카탈로그 메타 등록/조회/삭제 (RDBMS).
- F9: 질의 엔티티 → 카탈로그 `params_spec` 기반 동적 파라미터 매핑·조립.
- F10: 외부 공공 API On-demand 실시간 직접 호출(httpx) + JSON 파싱.
  서비스 키는 F5(`api_key_service`)에서 복호화해 주입하고, 응답에는 마스킹한다.
- F10 확장: 장애/타임아웃 감지 시 마지막 성공 스냅샷으로 로컬 우회(Fallback).
  성공 응답을 (catalog_id, params_hash) 단위로 캐시하고, 실패 시 캐시가 있으면
  source="local_fallback" 으로 반환한다(캐시 없으면 기존대로 502/504).
"""

from __future__ import annotations

import functools
import hashlib
import json
import time
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import PublicApiCatalog, PublicFetchCache
from ..schemas.public_data import CatalogCreate, FetchResponse
from ..security.crypto import mask
from ..utils import utcnow
from . import api_key_service

# ---------------------------------------------------------------- F6: 카탈로그


def register_catalog(db: Session, payload: CatalogCreate) -> PublicApiCatalog:
    dup = db.scalar(select(PublicApiCatalog).where(PublicApiCatalog.name == payload.name))
    if dup is not None:
        raise HTTPException(status_code=409, detail=f"이미 등록된 카탈로그: {payload.name}")
    row = PublicApiCatalog(
        name=payload.name,
        provider=payload.provider,
        domain=payload.domain,
        endpoint=payload.endpoint,
        http_method=payload.http_method.upper(),
        params_spec=[s.model_dump() for s in payload.params_spec],
        api_key_name=payload.api_key_name,
        api_key_param=payload.api_key_param,
        description=payload.description,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_catalogs(db: Session, domain: str | None = None) -> list[PublicApiCatalog]:
    stmt = select(PublicApiCatalog).order_by(PublicApiCatalog.id.desc())
    if domain:
        stmt = stmt.where(PublicApiCatalog.domain == domain)
    return list(db.scalars(stmt).all())


def get_catalog(db: Session, catalog_id: int) -> PublicApiCatalog:
    row = db.get(PublicApiCatalog, catalog_id)
    if row is None:
        raise HTTPException(status_code=404, detail="카탈로그를 찾을 수 없습니다.")
    return row


def delete_catalog(db: Session, catalog_id: int) -> None:
    row = get_catalog(db, catalog_id)
    db.delete(row)
    db.commit()


# ------------------------------------------------------- F9: 파라미터 매핑·조립


def _coerce(value: Any, type_: str, name: str) -> Any:
    try:
        if type_ == "int":
            return int(value)
        if type_ == "float":
            return float(value)
        if type_ == "bool":
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in ("true", "1", "y", "yes")
        return str(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail=f"파라미터 '{name}' 값을 {type_} 로 변환할 수 없습니다: {value!r}"
        ) from exc


def assemble_params(catalog: PublicApiCatalog, entities: dict[str, Any]) -> dict[str, Any]:
    """질의 엔티티 → params_spec 매핑·조립. 필수 누락 시 422 (spec 에 없는 엔티티는 무시)."""
    params: dict[str, Any] = {}
    for spec in catalog.params_spec or []:
        name = spec["name"]
        alias = spec.get("map_from")
        if alias and alias in entities:
            value = entities[alias]
        elif name in entities:
            value = entities[name]
        else:
            value = spec.get("default")
        if value is None:
            if spec.get("required"):
                raise HTTPException(status_code=422, detail=f"필수 파라미터 누락: {name}")
            continue
        params[name] = _coerce(value, spec.get("type", "str"), name)
    return params


# ------------------------------------------------- F10: On-demand 실시간 호출


@functools.lru_cache(maxsize=1)
def _http_client() -> httpx.Client:
    """공용 HTTP 클라이언트 — 요청마다 생성/해제 대신 커넥션 풀 재사용."""
    return httpx.Client(follow_redirects=True)


def _do_request(method: str, url: str, params: dict, timeout: float) -> tuple[int, Any]:
    """실 HTTP 호출 (테스트에서 monkeypatch 지점)."""
    res = _http_client().request(method, url, params=params, timeout=timeout)
    try:
        payload = res.json()
    except Exception:  # noqa: BLE001 — JSON 아님(XML/텍스트)
        payload = res.text
    return res.status_code, payload


def _extract_items(payload: Any) -> list | None:
    """공공데이터 응답에서 목록 추출 (data.go.kr 표준 경로 우선)."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    for path in (
        ("response", "body", "items", "item"),
        ("response", "body", "items"),
        ("items",),
    ):
        cur: Any = payload
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                cur = None
                break
        if isinstance(cur, list):
            return cur
        if isinstance(cur, dict):
            return [cur]
    return None


def _params_hash(catalog: PublicApiCatalog, params: dict[str, Any]) -> str:
    """캐시 키 — 서비스 키(시크릿)를 제외한 파라미터의 결정적 해시."""
    clean = {k: v for k, v in params.items() if k != catalog.api_key_param}
    raw = json.dumps(clean, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _save_cache(db: Session, catalog_id: int, params_hash: str, response: FetchResponse) -> None:
    """성공 응답 스냅샷 upsert (fallback 재료). 실패해도 본 응답에는 영향 없음."""
    try:
        row = db.scalar(
            select(PublicFetchCache).where(
                PublicFetchCache.catalog_id == catalog_id,
                PublicFetchCache.params_hash == params_hash,
            )
        )
        snapshot = response.model_dump(mode="json")
        if row is None:
            db.add(
                PublicFetchCache(
                    catalog_id=catalog_id, params_hash=params_hash, response=snapshot
                )
            )
        else:
            row.response = snapshot
            row.fetched_at = utcnow()
        db.commit()
    except Exception:  # noqa: BLE001 — 캐시 실패는 비치명
        db.rollback()


def _load_fallback(db: Session, catalog_id: int, params_hash: str) -> FetchResponse | None:
    """장애/타임아웃 시 마지막 성공 스냅샷 로드 (없으면 None)."""
    row = db.scalar(
        select(PublicFetchCache).where(
            PublicFetchCache.catalog_id == catalog_id,
            PublicFetchCache.params_hash == params_hash,
        )
    )
    if row is None:
        return None
    cached = FetchResponse(**row.response)
    cached.source = "local_fallback"
    cached.cached_at = row.fetched_at
    return cached


def fetch(db: Session, catalog_id: int, entities: dict[str, Any]) -> FetchResponse:
    catalog = get_catalog(db, catalog_id)
    params = assemble_params(catalog, entities)  # F9
    cache_key = _params_hash(catalog, params)

    masked_params = dict(params)
    if catalog.api_key_name:  # F5 연동: 복호화 주입 + 응답 마스킹
        secret = api_key_service.get_secret(db, catalog.api_key_name)
        params[catalog.api_key_param] = secret
        masked_params[catalog.api_key_param] = mask(secret)

    settings = get_settings()
    started = time.perf_counter()
    try:
        status_code, payload = _do_request(
            catalog.http_method, catalog.endpoint, params, settings.public_api_timeout_sec
        )
    except httpx.TimeoutException as exc:
        fallback = _load_fallback(db, catalog.id, cache_key)  # F10: 로컬 우회
        if fallback is not None:
            return fallback
        raise HTTPException(status_code=504, detail=f"공공 API 응답 지연: {catalog.name}") from exc
    except httpx.HTTPError as exc:
        fallback = _load_fallback(db, catalog.id, cache_key)
        if fallback is not None:
            return fallback
        raise HTTPException(status_code=502, detail=f"공공 API 호출 실패: {exc}") from exc

    if status_code >= 400:
        fallback = _load_fallback(db, catalog.id, cache_key)
        if fallback is not None:
            return fallback
        raise HTTPException(
            status_code=502,
            detail=f"공공 API 오류(HTTP {status_code}): {str(payload)[:300]}",
        )

    items = _extract_items(payload)
    data = None
    if items is None:
        data = payload if not isinstance(payload, str) else payload[:2000]

    response = FetchResponse(
        catalog_id=catalog.id,
        api_name=catalog.name,
        provider=catalog.provider,
        endpoint=catalog.endpoint,
        assembled_params=masked_params,
        status_code=status_code,
        items=items,
        data=data,
        elapsed_sec=round(time.perf_counter() - started, 3),
    )
    _save_cache(db, catalog.id, cache_key, response)  # fallback 재료 갱신
    return response
