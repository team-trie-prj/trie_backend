"""검색·보고서 이력 자동 로깅 — vikira 경로 앞단 ASGI 미들웨어 (F8 확장, FNC-HIS-01, 김예담).

vikira 코드를 수정하지 않고 `/api/v1/search`·`/api/v1/reports` 요청/응답을 관찰해
검색 트랜잭션·보고서 스냅샷을 동일 세션 UUID 로 히스토리에 기록한다.
- session_uuid: 요청 헤더 `X-Session-Id` → (reports는) body.session_id → 응답 session_id → 생성
- user_id: `Authorization: Bearer` 디코드(없으면 null)
- 성공(200) 응답만 기록. 로깅 실패는 요청을 깨지 않음(best-effort).
"""

from __future__ import annotations

import json
import uuid

from starlette.requests import Request

from .. import database
from ..services import history_service
from .jwt import ACCESS, decode_token

_SEARCH = "/api/v1/search"
_REPORT = "/api/v1/reports"


class SearchHistoryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path")
        if scope.get("type") != "http" or scope.get("method") != "POST" or path not in (_SEARCH, _REPORT):
            return await self.app(scope, receive, send)

        req_body = b""
        while True:
            message = await receive()
            req_body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        state = {"status": None}
        resp_chunks: list[bytes] = []

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
            elif message["type"] == "http.response.body":
                resp_chunks.append(message.get("body", b""))
            await send(message)

        sent = False

        async def replay_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": req_body, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send_wrapper)

        if state["status"] == 200:
            try:
                await _record(scope, path, req_body, b"".join(resp_chunks))
            except Exception:  # noqa: BLE001 — 로깅 실패는 무시
                pass


def _user_from_auth(auth: str | None) -> int | None:
    if not auth or not auth.lower().startswith("bearer "):
        return None
    try:
        payload = decode_token(auth.split(" ", 1)[1])
        return int(payload["sub"]) if payload.get("type") == ACCESS else None
    except Exception:  # noqa: BLE001
        return None


def _json(raw: bytes) -> dict:
    try:
        data = json.loads(raw or b"{}")
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


async def _extract_search(scope, body: bytes, ctype: str) -> tuple[str | None, str | None]:
    try:
        if "application/json" in ctype:
            d = _json(body)
            return (d.get("query") or d.get("text"), d.get("domain"))
        if "multipart/form-data" in ctype or "application/x-www-form-urlencoded" in ctype:
            async def _replay():
                return {"type": "http.request", "body": body, "more_body": False}

            form = await Request(scope, _replay).form()
            q = form.get("text") or form.get("query")
            dom = form.get("domain")
            return (q if isinstance(q, str) else None, dom if isinstance(dom, str) else None)
    except Exception:  # noqa: BLE001
        return (None, None)
    return (None, None)


async def _record(scope, path: str, req_body: bytes, resp_body: bytes) -> None:
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    user_id = _user_from_auth(headers.get("authorization"))
    resp = _json(resp_body)
    db = database.SessionLocal()  # 호출 시점 조회(테스트 재바인딩 대응)
    try:
        if path == _SEARCH:
            query, domain = await _extract_search(scope, req_body, headers.get("content-type", ""))
            if not query:
                return
            session_uuid = headers.get("x-session-id") or resp.get("session_id") or uuid.uuid4().hex
            history_service.record(db, session_uuid, query, domain, resp, user_id)
        else:  # /reports — 보고서 스냅샷을 동일 세션에 부착
            body = _json(req_body)
            session_uuid = (
                headers.get("x-session-id")
                or body.get("session_id")
                or body.get("session_uuid")
                or resp.get("session_id")
            )
            if not session_uuid:
                return
            history_service.record_report(db, session_uuid, resp, user_id, body.get("query"))
    finally:
        db.close()
