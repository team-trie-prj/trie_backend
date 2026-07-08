"""F10 확장 — 외부 API 장애/타임아웃 감지 로컬 우회(Fallback) 테스트."""

from __future__ import annotations

import httpx

CATALOG = {
    "name": "에어코리아-폴백",
    "endpoint": "https://api.example.com/air",
    "provider": "공공데이터포털",
    "domain": "traffic",
    "http_method": "GET",
    "params_spec": [
        {"name": "sidoName", "type": "str", "required": True, "map_from": "region"},
    ],
}


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_catalog(client, token) -> int:
    res = client.post("/public-data/catalog", headers=_hdr(token), json=CATALOG)
    return res.json()["data"]["id"]


def _fetch(client, token, cid):
    return client.post(
        f"/public-data/{cid}/fetch", headers=_hdr(token), json={"entities": {"region": "대전"}}
    )


def test_success_then_timeout_falls_back_to_cache(client, token, monkeypatch):
    from app.services import public_data_service

    cid = _make_catalog(client, token)

    # 1) 성공 호출 → 캐시 적재
    monkeypatch.setattr(
        public_data_service,
        "_do_request",
        lambda m, u, p, t: (200, {"items": [{"pm10": 41}]}),
    )
    r1 = _fetch(client, token, cid)
    assert r1.status_code == 200
    assert r1.json()["data"]["source"] == "live"

    # 2) 타임아웃 → 마지막 성공 스냅샷으로 우회
    def raise_timeout(m, u, p, t):
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(public_data_service, "_do_request", raise_timeout)
    r2 = _fetch(client, token, cid)
    assert r2.status_code == 200, r2.text
    data = r2.json()["data"]
    assert data["source"] == "local_fallback"
    assert data["items"] == [{"pm10": 41}]
    assert data["cached_at"] is not None


def test_upstream_5xx_falls_back_to_cache(client, token, monkeypatch):
    from app.services import public_data_service

    cid = _make_catalog(client, token)
    monkeypatch.setattr(
        public_data_service, "_do_request", lambda m, u, p, t: (200, {"items": [{"x": 1}]})
    )
    assert _fetch(client, token, cid).status_code == 200

    monkeypatch.setattr(
        public_data_service, "_do_request", lambda m, u, p, t: (500, "Internal Error")
    )
    r = _fetch(client, token, cid)
    assert r.status_code == 200
    assert r.json()["data"]["source"] == "local_fallback"


def test_timeout_without_cache_still_504(client, token, monkeypatch):
    from app.services import public_data_service

    cid = _make_catalog(client, token)

    def raise_timeout(m, u, p, t):
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(public_data_service, "_do_request", raise_timeout)
    r = _fetch(client, token, cid)
    assert r.status_code == 504  # 캐시 없음 → 기존 동작 유지


def test_cache_key_ignores_service_key(db):
    """서비스 키 로테이션이 캐시 키에 영향을 주지 않아야 한다."""
    from app.models import PublicApiCatalog
    from app.services.public_data_service import _params_hash

    cat = PublicApiCatalog(
        name="t", endpoint="https://e", params_spec=[], api_key_param="serviceKey"
    )
    h1 = _params_hash(cat, {"sidoName": "대전", "serviceKey": "KEY-A"})
    h2 = _params_hash(cat, {"sidoName": "대전", "serviceKey": "KEY-B"})
    h3 = _params_hash(cat, {"sidoName": "부산", "serviceKey": "KEY-A"})
    assert h1 == h2
    assert h1 != h3
