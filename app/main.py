"""FastAPI 애플리케이션 진입점."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import __version__
from .api import auth, documents, reports, search
from .config import get_settings
from .database import init_db


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

app.include_router(auth.router, prefix="/api/v1")
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
