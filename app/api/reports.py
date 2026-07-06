"""보고서 생성 API — 검색 근거 + 서식 결합 LLM 메타 프롬프팅 (FNC-REP-01)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from ..agent import run_agent
from ..database import get_db
from ..schemas.report import ReportRequest, ReportResponse
from ..search.schemas import SearchHit
from ..services.report_service import generate_report
from ..services.search_service import execute_search

router = APIRouter(tags=["reports"])


@router.post("/reports", response_model=ReportResponse)
def create_report(
    req: ReportRequest,
    x_session_id: str | None = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    """⑤ 검색 결과(또는 재검색) 근거로 도메인·타입별 실무 보고서 초안 생성.

    session_id 우선순위: 요청 body > X-Session-Id 헤더 > 서버 생성.
    """
    if req.hits:
        hits = [
            SearchHit(
                source=h.source, document_id=h.document_id, chunk_index=h.chunk_index,
                text=h.text, score=h.score, domain=h.domain,
            )
            for h in req.hits
        ]
    else:
        decision = run_agent(req.query, domain_hint=req.domain)
        route = decision.route if decision.route not in ("clarify", "public_api") else "hybrid"
        hits = execute_search(
            req.query, route=route, keywords=decision.keywords, domain=decision.domain, db=db
        ).hits

    return generate_report(
        req.query, hits, domain=req.domain, report_type=req.report_type,
        session_id=req.session_id or x_session_id, db=db,
    )
