"""세션 UUID API — [캐시 버그 차단] 매 쿼리 난수 세션 UUID 생성 (F8, 김예담).

매 호출마다 새 UUID4 를 발급하고 no-store 헤더를 강제하여
동일 결과 반복(캐시) 오류를 원천 차단한다.
(※ 세션 이력 로깅/복원은 본 범위 밖 — UUID 생성까지)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from ..schemas.public_data import SessionUUIDOut
from ..utils import utcnow

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionUUIDOut)
def create_session_uuid(response: Response) -> SessionUUIDOut:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return SessionUUIDOut(session_uuid=str(uuid.uuid4()), issued_at=utcnow())
