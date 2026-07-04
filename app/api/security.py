"""보안 API — 시스템 프롬프트 인젝션 1차 필터 사전 검사 (김예담).

프론트가 검색/보고서 요청(vikira) 전에 질의 텍스트를 1차 검사하는 용도.
업로드 문서 본문은 업로드 시점(`POST /documents`)에 자동 필터된다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..response import ApiResponse, ok
from ..schemas.security import PromptCheckRequest, PromptScanOut
from ..security.deps import get_current_user_id
from ..security.prompt_guard import scan_text

router = APIRouter(prefix="/security", tags=["security"])


@router.post("/prompt-check", response_model=ApiResponse[PromptScanOut])
def prompt_check(
    body: PromptCheckRequest,
    _uid: int = Depends(get_current_user_id),
) -> dict:
    """텍스트 프롬프트 인젝션 1차 검사 → {flagged, matches}."""
    res = scan_text(body.text)
    return ok(
        PromptScanOut(flagged=res.flagged, matches=res.matches),
        message="차단 권고" if res.flagged else "정상",
    )
