"""공공데이터 API — 카탈로그 등록/조회/삭제(F6) + On-demand 호출(F9·F10). 김예담."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.public_data import CatalogCreate, CatalogOut, FetchRequest, FetchResponse
from ..security.deps import get_current_user_id
from ..services import public_data_service

router = APIRouter(prefix="/public-data", tags=["public-data"])


@router.post("/catalog", response_model=CatalogOut)
def register_catalog(
    body: CatalogCreate,
    _uid: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CatalogOut:
    """오픈 API 카탈로그 메타 등록 (F6)."""
    return public_data_service.register_catalog(db, body)


@router.get("/catalog", response_model=list[CatalogOut])
def list_catalogs(domain: str | None = None, db: Session = Depends(get_db)) -> list:
    return public_data_service.list_catalogs(db, domain)


@router.get("/catalog/{catalog_id}", response_model=CatalogOut)
def get_catalog(catalog_id: int, db: Session = Depends(get_db)) -> CatalogOut:
    return public_data_service.get_catalog(db, catalog_id)


@router.delete("/catalog/{catalog_id}")
def delete_catalog(
    catalog_id: int,
    _uid: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    public_data_service.delete_catalog(db, catalog_id)
    return {"detail": "deleted", "catalog_id": catalog_id}


@router.post("/{catalog_id}/fetch", response_model=FetchResponse)
def fetch_public_data(
    catalog_id: int,
    body: FetchRequest,
    _uid: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> FetchResponse:
    """엔티티 → 파라미터 매핑·조립(F9) → 외부 공공 API 실시간 호출(F10)."""
    return public_data_service.fetch(db, catalog_id, body.entities)
