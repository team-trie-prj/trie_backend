"""FastAPI 애플리케이션 진입점."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .api import (
    api_keys,
    auth,
    document_transport,
    documents,
    public_data,
    reports,
    search,
    security,
    sessions,
)
from .config import get_settings
from .database import init_db
from .response import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 테이블 보장 (dev 편의; 운영은 Alembic 마이그레이션 권장)
    init_db()
    yield


settings = get_settings()

app = FastAPI(
    title="trie backend — Hybrid RAG",
    version=__version__,
    description="멀티모달 + 에이전트 기반 하이브리드 RAG 통합 검색 시스템 (BE)",
    lifespan=lifespan,
)

# 공통 응답 envelope 예외 핸들러 (김예담 경로에만 적용; vikira /api/v1 은 기본 {detail})
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# ── 김예담: 기능별 루트 경로 (/auth /documents /api-keys /public-data /sessions) ──
app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(document_transport.router)
app.include_router(public_data.router)
app.include_router(sessions.router)
app.include_router(security.router)

# ── vikira: 기존 /api/v1 경로 유지 ──
app.include_router(documents.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")


@app.get("/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": __version__,
        "embedding_backend": settings.embedding_backend,
        "chunk_strategy": settings.chunk_strategy,
    }
