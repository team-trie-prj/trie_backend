"""인증 API 테스트 — mock provider (오프라인, 카카오 키 불필요).

kakao_client_id 미설정 → resolved_auth_provider == "mock" 로 폴백되어
실제 카카오 호출 없이 로그인/갱신/로그아웃 전 플로우를 검증한다.
(client/db 픽스처는 tests/conftest.py 공용 사용)
"""

from __future__ import annotations

from sqlalchemy import select


def test_kakao_login_issues_tokens_and_creates_user(client):
    res = client.post("/auth/kakao", json={"code": "dummy-1"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["expires_in"] > 0
    assert body["user"]["provider"] == "kakao"
    assert body["user"]["id"] >= 1


def test_login_is_idempotent_upsert(client):
    r1 = client.post("/auth/kakao", json={"code": "same-code"})
    r2 = client.post("/auth/kakao", json={"code": "same-code"})
    assert r1.json()["user"]["id"] == r2.json()["user"]["id"]


def test_refresh_returns_new_access_token(client):
    login = client.post("/auth/kakao", json={"code": "c2"}).json()
    res = client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert res.status_code == 200, res.text
    assert res.json()["access_token"]


def test_logout_revokes_refresh_token(client):
    login = client.post("/auth/kakao", json={"code": "c3"}).json()
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


def test_logout_requires_auth(client):
    assert client.post("/auth/logout").status_code == 401


def test_refresh_token_stored_hashed_not_plaintext(client, db):
    """리프레시 토큰은 DB 에 SHA-256 해시로만 저장(평문 금지)."""
    from app.models import RefreshToken

    login = client.post("/auth/kakao", json={"code": "hash-check"}).json()
    raw = login["refresh_token"]
    rows = db.scalars(select(RefreshToken)).all()
    assert rows
    assert all(r.token != raw for r in rows)      # 평문 미저장
    assert all(len(r.token) == 64 for r in rows)  # sha256 hexdigest
    # 해시 저장 상태에서도 갱신 플로우 정상
    assert client.post("/auth/refresh", json={"refresh_token": raw}).status_code == 200


def test_stale_tokens_purged_on_login(client, db):
    """로그인 시 만료·폐기 토큰 정리 → 테이블 무한 증가 방지."""
    from app.models import RefreshToken

    first = client.post("/auth/kakao", json={"code": "purge-1"}).json()
    client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )  # 사용자의 모든 토큰 revoked
    client.post("/auth/kakao", json={"code": "purge-1"})  # 재로그인 → purge + 신규 1개

    uid = first["user"]["id"]
    rows = db.scalars(select(RefreshToken).where(RefreshToken.user_id == uid)).all()
    assert len(rows) == 1
    assert rows[0].revoked is False
