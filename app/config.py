"""애플리케이션 설정 (.env 로딩)."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_name: str = "trie-backend"
    debug: bool = True

    # --- Database (RDBMS) ---
    database_url: str = "sqlite:///./data/trie.db"

    # --- Storage ---
    upload_dir: str = "./data/uploads"
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection: str = "knowledge_documents"

    # --- ③ Embedding (BGE-m3, local/free) ---
    embedding_backend: str = "bge-m3"  # bge-m3 | hashing
    embedding_model_name: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 16

    # --- ② Chunking ---
    chunk_strategy: str = "semantic"  # semantic | recursive
    chunk_max_chars: int = 1000
    chunk_min_chars: int = 200
    chunk_overlap_sentences: int = 1
    semantic_breakpoint_percentile: int = 90

    # --- LLM / VLM (phases ②③⑤) ---
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.0-flash"
    vlm_model: str = "gemini-2.0-flash"
    gemini_api_key: str = ""

    def ensure_dirs(self) -> None:
        """로컬 데이터 디렉터리 보장 (sqlite / uploads / chroma)."""
        for path in (self.upload_dir, self.chroma_persist_dir):
            os.makedirs(path, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            db_path = self.database_url.replace("sqlite:///", "", 1)
            parent = os.path.dirname(db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
