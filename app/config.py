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
    max_upload_mb: int = 50  # 문서 업로드 파일당 용량 한도 (F2, 초과 시 413)
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

    # --- ③ Agent ---
    agent_ambiguity_threshold: float = 0.5

    # --- ④ Search / Rerank ---
    rerank_backend: str = "cross-encoder"  # cross-encoder | none
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    search_top_k: int = 20  # 재정렬 전 후보 수
    search_final_k: int = 8  # 재정렬/절삭 후 최종 수
    context_max_tokens: int = 3000  # LLM 컨텍스트 절삭 예산

    # --- LLM / VLM (phases ②③⑤) ---
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash"
    vlm_model: str = "gemini-2.5-flash"
    gemini_api_key: str = ""
    llm_timeout_sec: float = 60.0  # LLM/VLM 호출 타임아웃 (S7: 60초 초과 시 하이브리드 폴백)

    # --- Auth: OAuth2 (Kakao) --- (김예담)
    auth_provider: str = "kakao"  # kakao | mock  (client_id 없으면 mock 자동 폴백)
    kakao_client_id: str = ""
    kakao_client_secret: str = ""
    kakao_redirect_uri: str = "http://localhost:5173/oauth/kakao/callback"
    kakao_token_url: str = "https://kauth.kakao.com/oauth/token"
    kakao_userinfo_url: str = "https://kapi.kakao.com/v2/user/me"

    # --- Auth: JWT ---
    jwt_secret_key: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    # --- Security: 민감정보 암호화 (F5, Fernet) ---
    app_encryption_key: str = ""  # 비면 jwt_secret_key 에서 파생

    # --- Security: 프롬프트 인젝션 1차 필터 ---
    prompt_injection_filter_enabled: bool = True

    # --- CORS (FE 연동 허용 오리진 화이트리스트, 콤마 구분) ---
    cors_allow_origins: str = "http://localhost:5173"

    # --- 검색 이력 (F8 확장, FNC-HIS-01) ---
    history_max_per_user: int = 50  # 사용자별 이력 상한(초과 시 최고참부터 FIFO 삭제)

    # --- Public Data (F10) ---
    public_api_timeout_sec: float = 10.0
    public_data_service_key: str = ""  # data.go.kr 서비스키(Decoding). 실값은 .env(커밋 금지), 목록조회/카탈로그 시드용

    @property
    def resolved_auth_provider(self) -> str:
        """client_id 미설정 시 mock 폴백 (vikira LLM mock 패턴과 동일)."""
        if self.auth_provider == "kakao" and not self.kakao_client_id:
            return "mock"
        return self.auth_provider

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
