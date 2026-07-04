"""질의 프롬프트 인젝션 필터 — vikira 검색/보고서 경로 앞단 ASGI 미들웨어 (김예담).

vikira 코드를 **전혀 수정하지 않고**, 요청이 vikira 라우트 핸들러에 닿기 전에
질의 텍스트를 1차(규칙 기반) 필터한다.

- 대상 경로: POST /api/v1/search, /api/v1/search/analyze (form `text`), /api/v1/reports (json `query`)
- 의심 시: `400` 으로 차단(vikira 미도달). 정상: 원문 body 그대로 downstream 통과.
- 파싱 실패는 통과(fail-open) — 검색 가용성 우선, 어차피 vikira 가 형식 검증.
- 토글: `PROMPT_INJECTION_FILTER_ENABLED` (F11 공용 스위치).
"""

from __future__ import annotations

import json

from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import get_settings
from .prompt_guard import scan_text

# vikira 소유. 질의 텍스트가 유입되는 엔드포인트만 앞단 필터.
GUARDED_PATHS = {"/api/v1/search", "/api/v1/search/analyze", "/api/v1/reports"}


class PromptInjectionMiddleware:
    """vikira 검색/보고서 질의에 대한 1차 인젝션 필터 (앞단, 비침투)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in GUARDED_PATHS
            or not get_settings().prompt_injection_filter_enabled
        ):
            return await self.app(scope, receive, send)

        # 요청 body 버퍼링 (downstream 재생용)
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        text = await _extract_query(scope, body)
        result = scan_text(text)
        if result.flagged:
            response = JSONResponse(
                status_code=400,
                content={
                    "detail": "프롬프트 인젝션 의심 질의가 차단되었습니다.",
                    "code": "PROMPT_INJECTION_BLOCKED",
                    "matches": result.matches,
                },
            )
            await response(scope, receive, send)
            return

        # 정상 → 버퍼링한 body 를 그대로 재생하여 vikira 로 전달
        sent = False

        async def replay_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)


async def _extract_query(scope, body: bytes) -> str | None:
    """요청 본문에서 질의 텍스트(`query`/`text`) 추출. 실패 시 None(fail-open)."""
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    ctype = headers.get("content-type", "")
    try:
        if "application/json" in ctype:
            data = json.loads(body or b"{}")
            return (data.get("query") or data.get("text")) if isinstance(data, dict) else None
        if "multipart/form-data" in ctype or "application/x-www-form-urlencoded" in ctype:
            async def _replay():
                return {"type": "http.request", "body": body, "more_body": False}

            form = await Request(scope, _replay).form()
            value = form.get("text") or form.get("query")
            return value if isinstance(value, str) else None
    except Exception:  # noqa: BLE001 — 파싱 실패는 통과
        return None
    return None
