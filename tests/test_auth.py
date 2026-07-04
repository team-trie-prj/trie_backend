"""인증 API 테스트 — mock provider (오프라인, 카카오 키 불필요).

응답은 공통 envelope({success, code, message, data}) — 실제 페이로드는 `data` 아래.
(client/db 픽스처는 tests/conftest.py 공용 사용)
"""

from __future__ import annotations

from sqlalchemy import select


def test_kakao_login_issues_tokens_and_creates_user(client):
    res = client.post("/auth/kakao", json={"code": "dummy-1"})
    assert res.status_code == 200, res.text
    env = res.json()
    assert env["success"] is True and env["code"] == "OK"
    data = env["data"]
    assert data["token_type"] == "bearer"
    assert data["access_token"] and data["refresh_token"]
    assert data["expires_in"] > 0
    assert data["user"]["provider"] == "kakao"
    assert data["user"]["id"] >= 1


def test_login_is_idempotent_upsert(client):
    r1 = client.post("/auth/kakao", json={"code": "same-code"})
    r2 = client.post("/auth/kakao", json={"code": "same-code"})
    assert r1.json()["data"]["user"]["id"] == r2.json()["data"]["user"]["id"]


def test_refresh_returns_new_access_token(client):
    login = client.post("/auth/kakao", json={"code": "c2"}).json()["data"]
    res = client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert res.status_code == 200, res.text
    assert res.json()["data"]["access_token"]


def test_logout_revokes_refresh_token(client):
    login = client.post("/auth/kakao", json={"code": "c3"}).json()["data"]
    out = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert out.status_code == 200, out.text
    # 폐기 후 refresh 는 401
    again = client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert again.status_code == 401


def test_refresh_rejects_garbage_token(client):
    res = client.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert res.status_code == 401
    # 에러도 envelope 형식
    body = res.json()
    assert body["success"] is False and body["code"] == "UNAUTHORIZED"


def test_logout_requires_auth(client):
    res = client.post("/auth/logout")
    assert res.status_code == 401
    assert res.json()["success"] is False


def test_refresh_token_stored_hashed_not_plaintext(client, db):
    """리프레시 토큰은 DB 에 SHA-256 해시로만 저장(평문 금지)."""
    from app.models import RefreshToken

    login = client.post("/auth/kakao", json={"code": "hash-check"}).json()["data"]
    raw = login["refresh_token"]
    rows = db.scalars(select(RefreshToken)).all()
    assert rows
    assert all(r.token != raw for r in rows)      # 평문 미저장
    assert all(len(r.token) == 64 for r in rows)  # sha256 hexdigest
    assert client.post("/auth/refresh", json={"refresh_token": raw}).status_code == 200


def test_stale_tokens_purged_on_login(client, db):
    """로그인 시 만료·폐기 토큰 정리 → 테이블 무한 증가 방지."""
    from app.models import RefreshToken

    first = client.post("/auth/kakao", json={"code": "purge-1"}).json()["data"]
    client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )  # 사용자의 모든 토큰 revoked
    client.post("/auth/kakao", json={"code": "purge-1"})  # 재로그인 → purge + 신규 1개

    uid = first["user"]["id"]
    rows = db.scalars(select(RefreshToken).where(RefreshToken.user_id == uid)).all()
    assert len(rows) == 1
    assert rows[0].revoked is False
