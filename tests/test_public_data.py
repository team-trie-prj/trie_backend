"""공공데이터 (F6 카탈로그 · F9 파라미터 매핑 · F10 On-demand 호출) — 외부 HTTP 는 스텁. (응답 envelope)"""

from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException


def _hdr(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


CATALOG = {
    "name": "에어코리아 대기오염정보",
    "provider": "한국환경공단",
    "domain": "traffic",
    "endpoint": "http://apis.example.com/air",
    "params_spec": [
        {"name": "sidoName", "type": "str", "required": True, "map_from": "region"},
        {"name": "numOfRows", "type": "int", "required": False, "default": 10},
        {"name": "returnType", "type": "str", "required": False, "default": "json"},
    ],
}


# ------------------------------------------------------------------- F6


def test_catalog_requires_auth(client):
    assert client.post("/public-data/catalog", json=CATALOG).status_code == 401


def test_catalog_crud(client, token):
    r = client.post("/public-data/catalog", headers=_hdr(token), json=CATALOG)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    cid = data["id"]
    assert data["params_spec"][0]["name"] == "sidoName"

    # 중복 등록 → 409
    dup = client.post("/public-data/catalog", headers=_hdr(token), json=CATALOG)
    assert dup.status_code == 409
    assert dup.json()["code"] == "CONFLICT"

    lst = client.get("/public-data/catalog").json()["data"]
    assert any(c["id"] == cid for c in lst)
    assert client.get(f"/public-data/catalog/{cid}").status_code == 200
    assert client.get("/public-data/catalog?domain=road").json()["data"] == []

    assert client.delete(f"/public-data/catalog/{cid}", headers=_hdr(token)).status_code == 200
    assert client.get(f"/public-data/catalog/{cid}").status_code == 404


# ------------------------------------------------------------------- F9


def _make_catalog(**over):
    from app.models import PublicApiCatalog

    base = dict(
        name="c", endpoint="http://x", http_method="GET", api_key_param="serviceKey",
        params_spec=CATALOG["params_spec"],
    )
    base.update(over)
    return PublicApiCatalog(**base)


def test_assemble_maps_alias_and_defaults():
    from app.services.public_data_service import assemble_params

    params = assemble_params(_make_catalog(), {"region": "대전"})
    assert params == {"sidoName": "대전", "numOfRows": 10, "returnType": "json"}


def test_assemble_coerces_types_and_ignores_unknown():
    from app.services.public_data_service import assemble_params

    params = assemble_params(_make_catalog(), {"sidoName": "부산", "numOfRows": "25", "지원안함": 1})
    assert params["numOfRows"] == 25
    assert "지원안함" not in params


def test_assemble_missing_required_422():
    from app.services.public_data_service import assemble_params

    with pytest.raises(HTTPException) as e:
        assemble_params(_make_catalog(), {})
    assert e.value.status_code == 422
    assert "sidoName" in e.value.detail


def test_assemble_bad_type_422():
    from app.services.public_data_service import assemble_params

    with pytest.raises(HTTPException) as e:
        assemble_params(_make_catalog(), {"region": "대전", "numOfRows": "많이"})
    assert e.value.status_code == 422


# ------------------------------------------------------------------- F10


@pytest.fixture()
def catalog_id(client, token):
    return client.post("/public-data/catalog", headers=_hdr(token), json=CATALOG).json()["data"]["id"]


def test_fetch_requires_auth(client, catalog_id):
    r = client.post(f"/public-data/{catalog_id}/fetch", json={"entities": {}})
    assert r.status_code == 401


def test_fetch_extracts_items_and_masks_key(client, token, catalog_id, monkeypatch):
    from app.services import public_data_service

    # F5 연동: 서비스 키 등록 후 카탈로그에 연결
    client.post("/api-keys", headers=_hdr(token), json={"name": "datago", "secret": "REAL-KEY-123"})

    captured: dict = {}

    def fake_request(method, url, params, timeout):
        captured.update({"method": method, "url": url, "params": dict(params)})
        return 200, {"response": {"body": {"items": {"item": [{"pm10": 41}, {"pm10": 33}]}}}}

    monkeypatch.setattr(public_data_service, "_do_request", fake_request)

    cat2 = dict(CATALOG, name="에어코리아-키연동", api_key_name="datago")
    cid2 = client.post("/public-data/catalog", headers=_hdr(token), json=cat2).json()["data"]["id"]

    r = client.post(
        f"/public-data/{cid2}/fetch", headers=_hdr(token),
        json={"entities": {"region": "대전"}},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["items"] == [{"pm10": 41}, {"pm10": 33}]                 # 표준 경로 파싱
    assert captured["params"]["serviceKey"] == "REAL-KEY-123"            # 실제 호출엔 평문 주입
    assert data["assembled_params"]["serviceKey"] != "REAL-KEY-123"      # 응답엔 마스킹
    assert "REAL-KEY-123" not in r.text
    assert captured["params"]["sidoName"] == "대전"                       # F9 매핑 결과 사용


def test_fetch_timeout_504(client, token, catalog_id, monkeypatch):
    from app.services import public_data_service

    def raise_timeout(method, url, params, timeout):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(public_data_service, "_do_request", raise_timeout)
    r = client.post(
        f"/public-data/{catalog_id}/fetch", headers=_hdr(token),
        json={"entities": {"region": "대전"}},
    )
    assert r.status_code == 504
    assert r.json()["code"] == "GATEWAY_TIMEOUT"


def test_fetch_upstream_error_502(client, token, catalog_id, monkeypatch):
    from app.services import public_data_service

    monkeypatch.setattr(public_data_service, "_do_request", lambda m, u, p, t: (500, "Internal"))
    r = client.post(
        f"/public-data/{catalog_id}/fetch", headers=_hdr(token),
        json={"entities": {"region": "대전"}},
    )
    assert r.status_code == 502


def test_fetch_missing_required_422(client, token, catalog_id):
    r = client.post(
        f"/public-data/{catalog_id}/fetch", headers=_hdr(token), json={"entities": {}}
    )
    assert r.status_code == 422
