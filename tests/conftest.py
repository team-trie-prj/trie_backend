"""공용 테스트 픽스처 — 인메모리 SQLite + TestClient (김예담 파트)."""

from __future__ import annotations

import os
import tempfile

# 테스트는 항상 mock provider 사용(.env 에 실제 카카오 키가 있어도 실 API 호출 방지).
# app 임포트(=get_settings 캐싱) 이전에 환경변수를 비워 mock 으로 강제한다.
os.environ["KAKAO_CLIENT_ID"] = ""
os.environ["KAKAO_CLIENT_SECRET"] = ""
os.environ.setdefault("EMBEDDING_BACKEND", "hashing")
os.environ.setdefault("LLM_PROVIDER", "mock")
# 테스트 산출물(chroma/uploads)을 임시 디렉터리로 격리해 레포 오염 방지
_TEST_TMP = tempfile.mkdtemp(prefix="trie_test_")
os.environ.setdefault("CHROMA_PERSIST_DIR", os.path.join(_TEST_TMP, "chroma"))
os.environ.setdefault("UPLOAD_DIR", os.path.join(_TEST_TMP, "uploads"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def SessionLocal(_engine):
    return sessionmaker(bind=_engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db(SessionLocal):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(SessionLocal, monkeypatch):
    import app.database as database_module

    # 미들웨어(app.database.SessionLocal 직접 사용)도 테스트 DB 를 쓰도록 재바인딩
    monkeypatch.setattr(database_module, "SessionLocal", SessionLocal)

    def _override_get_db():
        d = SessionLocal()
        try:
            yield d
        finally:
            d.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def token(client) -> str:
    """mock 카카오 로그인으로 발급된 access token (응답 envelope의 data 아래)."""
    res = client.post("/auth/kakao", json={"code": "test-code"})
    return res.json()["data"]["access_token"]
