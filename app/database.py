"""SQLAlchemy 엔진 / 세션 / Base 정의.

RDBMS 는 spec 상 PostgreSQL 이지만, 로컬 개발은 SQLite 로 무설정 구동 가능.
DATABASE_URL 만 바꾸면 그대로 PostgreSQL 로 전환된다.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI 의존성 주입용 DB 세션."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """테이블 생성 (모델 등록 후 metadata.create_all)."""
    from . import models  # noqa: F401  (모델 등록 목적)

    Base.metadata.create_all(bind=engine)
