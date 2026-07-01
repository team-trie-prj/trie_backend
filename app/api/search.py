"""통합 검색 API — 멀티모달 분석 · 에이전트 라우팅 · 하이브리드 검색.

검증된 서비스 계층(multimodal · agent · search_service)을 얇게 감싼다.
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ..agent import run_agent
from ..config import get_settings
from ..database import get_db
from ..schemas.search import AnalyzeResponse, SearchResponse
from ..services.multimodal import analyze_multimodal
from ..services.search_service import execute_search

router = APIRouter(tags=["search"])


async def _save_image(image: UploadFile | None) -> str | None:
    if image is None:
        return None
    settings = get_settings()
    ext = os.path.splitext(image.filename or "")[1].lower() or ".jpg"
    path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as f:
        f.write(await image.read())
    return path


@router.post("/search/analyze", response_model=AnalyzeResponse)
async def analyze_query(
    text: str = Form(...),
    domain: str = Form("etc"),
    image: UploadFile | None = File(None),
) -> dict:
    """② 멀티모달 질의 분석 — 텍스트(+이미지)를 통합 쿼리로 병합."""
    image_path = await _save_image(image)
    return analyze_multimodal(text, image_path=image_path, domain=domain).as_dict()


@router.post("/search", response_model=SearchResponse)
async def integrated_search(
    text: str = Form(...),
    domain: str = Form("etc"),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
) -> dict:
    """③④ 통합 검색 — (이미지→VLM) 병합 → 라우팅 → 하이브리드 검색 → 재정렬 → 절삭."""
    image_path = await _save_image(image)

    if image_path:
        unified = analyze_multimodal(text, image_path=image_path, domain=domain)
        query, hint, seed_keywords = unified.unified_query, unified.domain_hint, unified.keywords
    else:
        query, hint, seed_keywords = text, domain, None

    decision = run_agent(query, domain_hint=hint)
    if decision.route == "clarify":
        return {"agent": decision.as_dict(), "search": None}

    result = execute_search(
        query,
        route=decision.route,
        keywords=decision.keywords or seed_keywords,
        domain=decision.domain,
        db=db,
    )
    return {"agent": decision.as_dict(), "search": result.as_dict()}
