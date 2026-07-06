"""검색 이력 자동 로깅 — vikira `/api/v1/search` 앞단 ASGI 미들웨어 (F8 확장, 김예담).

vikira 코드를 수정하지 않고, `/api/v1/search` 요청/응답을 관찰해 검색 트랜잭션을 기록한다.
- session_uuid: 요청 헤더 `X-Session-Id`(없으면 생성)
- user_id: `Authorization: Bearer` 디코드(없으면 null — 무인증 검색)
- 성공(200) 응답만 기록. 로깅 실패는 검색을 깨지 않음(best-effort).
"""

from __future__ import annotations

import json
import uuid

from starlette.requests import Request

from .. import database
from ..services import history_service
from .jwt import ACCESS, decode_token


class SearchHistoryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") != "POST" or scope.get("path") != "/api/v1/search":
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
                await _record(scope, req_body, b"".join(resp_chunks))
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


async def _extract(scope, body: bytes, headers: dict) -> tuple[str | None, str | None]:
    ctype = headers.get("content-type", "")
    try:
        if "application/json" in ctype:
            data = json.loads(body or b"{}")
            if isinstance(data, dict):
                return (data.get("query") or data.get("text"), data.get("domain"))
            return (None, None)
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


async def _record(scope, req_body: bytes, resp_body: bytes) -> None:
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    query, domain = await _extract(scope, req_body, headers)
    if not query:
        return
    session_uuid = headers.get("x-session-id") or uuid.uuid4().hex
    user_id = _user_from_auth(headers.get("authorization"))
    try:
        snapshot = json.loads(resp_body or b"{}")
    except Exception:  # noqa: BLE001
        snapshot = {}

    db = database.SessionLocal()  # 호출 시점 조회(테스트에서 재바인딩 가능)
    try:
        history_service.record(db, session_uuid, query, domain, snapshot, user_id)
    finally:
        db.close()
