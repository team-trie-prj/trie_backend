"""세션 UUID (F8) — 매 쿼리 난수 UUID + no-store 헤더."""

from __future__ import annotations

import uuid


def test_session_uuid_is_valid_and_unique(client):
    r1 = client.post("/sessions")
    r2 = client.post("/sessions")
    assert r1.status_code == 200 and r2.status_code == 200
    u1, u2 = r1.json()["session_uuid"], r2.json()["session_uuid"]
    assert uuid.UUID(u1).version == 4
    assert u1 != u2  # 매 쿼리 난수 — 캐시 버그 차단


def test_session_response_no_store_header(client):
    r = client.post("/sessions")
    assert "no-store" in r.headers.get("cache-control", "")
    assert r.json()["issued_at"]
