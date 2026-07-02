"""인증 API 테스트 — mock provider (오프라인, 카카오 키 불필요).

kakao_client_id 미설정 → resolved_auth_provider == "mock" 로 폴백되어
실제 카카오 호출 없이 로그인/갱신/로그아웃 전 플로우를 검증한다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_kakao_login_issues_tokens_and_creates_user(client):
    res = client.post("/api/v1/auth/kakao", json={"code": "dummy-1"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["expires_in"] > 0
    assert body["user"]["provider"] == "kakao"
    assert body["user"]["id"] >= 1


def test_login_is_idempotent_upsert(client):
    r1 = client.post("/api/v1/auth/kakao", json={"code": "same-code"})
    r2 = client.post("/api/v1/auth/kakao", json={"code": "same-code"})
    assert r1.json()["user"]["id"] == r2.json()["user"]["id"]


def test_refresh_returns_new_access_token(client):
    login = client.post("/api/v1/auth/kakao", json={"code": "c2"}).json()
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert res.status_code == 200, res.text
    assert res.json()["access_token"]


def test_logout_revokes_refresh_token(client):
    login = client.post("/api/v1/auth/kakao", json={"code": "c3"}).json()
    out = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert out.status_code == 200, out.text
    # 폐기 후 refresh 는 401
    again = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert again.status_code == 401


def test_refresh_rejects_garbage_token(client):
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert res.status_code == 401


def test_logout_requires_auth(client):
    assert client.post("/api/v1/auth/logout").status_code == 401
