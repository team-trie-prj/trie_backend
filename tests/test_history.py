"""검색 이력 (F8 확장, FNC-HIS-01) — 로깅·목록·스냅샷 복원·FIFO·유저 스코프·자동 로깅."""

from __future__ import annotations


def _hdr(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def test_log_list_and_snapshot(client, token):
    r = client.post("/history", headers=_hdr(token), json={
        "session_uuid": "sess-1", "query": "포트홀 보수 절차", "domain": "road",
        "result_snapshot": {"search": {"hits": [{"text": "포트홀은 ..."}]}},
    })
    assert r.status_code == 200, r.text
    lst = client.get("/history", headers=_hdr(token)).json()["data"]
    assert any(h["session_uuid"] == "sess-1" and h["query"] == "포트홀 보수 절차" for h in lst)
    snap = client.get("/history/sess-1", headers=_hdr(token))
    assert snap.status_code == 200
    assert snap.json()["data"]["result_snapshot"]["search"]["hits"]


def test_history_requires_auth(client):
    assert client.get("/history").status_code == 401
    assert client.post("/history", json={"session_uuid": "x", "query": "q"}).status_code == 401


def test_history_not_found(client, token):
    assert client.get("/history/does-not-exist", headers=_hdr(token)).status_code == 404


def test_fifo_eviction(client, token, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "history_max_per_user", 2)
    for i in range(3):
        client.post("/history", headers=_hdr(token), json={"session_uuid": f"s{i}", "query": f"q{i}"})
    lst = client.get("/history", headers=_hdr(token)).json()["data"]
    uuids = {h["session_uuid"] for h in lst}
    assert len(lst) == 2
    assert "s0" not in uuids and "s2" in uuids  # 오래된 s0 이 FIFO 로 제거


def test_upsert_same_session(client, token):
    client.post("/history", headers=_hdr(token), json={"session_uuid": "dup", "query": "first"})
    client.post("/history", headers=_hdr(token), json={"session_uuid": "dup", "query": "second"})
    lst = [h for h in client.get("/history", headers=_hdr(token)).json()["data"] if h["session_uuid"] == "dup"]
    assert len(lst) == 1 and lst[0]["query"] == "second"  # 중복 미생성 + 갱신


def test_history_user_scoped(client, token):
    client.post("/history", headers=_hdr(token), json={"session_uuid": "u1-only", "query": "u1"})
    t2 = client.post("/auth/kakao", json={"code": "other-user"}).json()["data"]["access_token"]
    u2 = client.get("/history", headers=_hdr(t2)).json()["data"]
    assert all(h["session_uuid"] != "u1-only" for h in u2)  # 타 사용자 이력 비노출
    assert client.get("/history/u1-only", headers=_hdr(t2)).status_code == 404


def test_delete_history(client, token):
    client.post("/history", headers=_hdr(token), json={"session_uuid": "del-1", "query": "q"})
    assert client.delete("/history/del-1", headers=_hdr(token)).status_code == 200
    assert client.get("/history/del-1", headers=_hdr(token)).status_code == 404


def test_autolog_via_search_middleware(client, token):
    """vikira /search 호출이 미들웨어로 자동 로깅되어 이력에 남는다(비침투)."""
    r = client.post("/api/v1/search", headers={**_hdr(token), "X-Session-Id": "auto-1"},
                    data={"text": "포트홀 보수 절차", "domain": "road"})
    assert r.status_code == 200, r.text
    lst = client.get("/history", headers=_hdr(token)).json()["data"]
    assert any(h["session_uuid"] == "auto-1" and "포트홀" in h["query"] for h in lst)


def test_default_fifo_cap_is_50():
    """인수기준: 사용자당 보존 상한 50."""
    from app.config import get_settings

    assert get_settings().history_max_per_user == 50


def test_restore_sets_no_store_header(client, token):
    """인수기준: 이력 클릭 시 캐시 무효화 후 1회성 조회."""
    client.post("/history", headers=_hdr(token), json={"session_uuid": "ns-1", "query": "q"})
    r = client.get("/history/ns-1", headers=_hdr(token))
    assert "no-store" in r.headers.get("cache-control", "")
    assert "no-store" in client.get("/history", headers=_hdr(token)).headers.get("cache-control", "")


def test_report_snapshot_attached_to_session(db):
    """서비스: 보고서 스냅샷이 동일 session_uuid 이력에 부착(검색 스냅샷 보존)."""
    from app.services import history_service

    history_service.record(db, "combo-1", "포트홀 보수", "road", {"search": {"hits": [1]}}, user_id=1)
    history_service.record_report(db, "combo-1", {"report": {"content": "# 점검 일지"}}, user_id=1)
    row = history_service.get_for_user(db, "combo-1", 1)
    assert row.result_snapshot["search"]["hits"] == [1]      # 검색 스냅샷 보존
    assert row.report_snapshot["report"]["content"].startswith("#")  # 보고서 스냅샷 부착


def test_report_autolog_via_middleware(client, token):
    """vikira /reports 완료가 같은 세션 이력에 보고서 스냅샷으로 자동 부착된다."""
    client.post("/api/v1/search", headers={**_hdr(token), "X-Session-Id": "rep-1"},
                data={"text": "포트홀 보수 절차", "domain": "road"})
    r = client.post("/api/v1/reports", headers={**_hdr(token), "X-Session-Id": "rep-1"},
                    json={"domain": "road", "report_type": "inspection_log", "query": "포트홀 보수 절차"})
    assert r.status_code == 200, r.text
    detail = client.get("/history/rep-1", headers=_hdr(token)).json()["data"]
    assert detail["report_snapshot"] is not None
