"""API Key (F5) — 암호화 저장 · 마스킹 · 복호화 · 인증."""

from __future__ import annotations

from sqlalchemy import select


def _hdr(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def test_encrypt_decrypt_roundtrip():
    from app.security.crypto import decrypt, encrypt

    cipher = encrypt("hello-키-123")
    assert cipher != "hello-키-123"
    assert decrypt(cipher) == "hello-키-123"


def test_service_stores_ciphertext_and_decrypts(db):
    from app.models import ApiKey
    from app.services import api_key_service

    api_key_service.register(db, "data_go_kr", "PLAINTEXT-XYZ", "data.go.kr", "공공데이터 키")
    row = db.scalar(select(ApiKey).where(ApiKey.name == "data_go_kr"))
    assert row is not None
    assert "PLAINTEXT-XYZ" not in row.secret_encrypted  # RDBMS 암호화 저장
    assert api_key_service.get_secret(db, "data_go_kr") == "PLAINTEXT-XYZ"  # 복호화


def test_register_endpoint_masks_secret(client, token):
    r = client.post(
        "/api-keys",
        headers=_hdr(token),
        json={"name": "k1", "provider": "p", "secret": "SUPER-SECRET-123"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "SUPER-SECRET-123" not in str(body)  # 평문 비노출
    assert body["secret_preview"].startswith("SUPE")


def test_list_and_delete(client, token):
    client.post("/api-keys", headers=_hdr(token), json={"name": "k2", "secret": "s2secret"})
    lst = client.get("/api-keys", headers=_hdr(token)).json()
    assert any(k["name"] == "k2" for k in lst)
    assert all("s2secret" not in str(k) for k in lst)  # 평문 미노출
    assert client.delete("/api-keys/k2", headers=_hdr(token)).status_code == 200
    assert client.delete("/api-keys/k2", headers=_hdr(token)).status_code == 404


def test_requires_auth(client):
    assert client.get("/api-keys").status_code == 401
    assert client.post("/api-keys", json={"name": "x", "secret": "y"}).status_code == 401
