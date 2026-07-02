# 기술 스택 (김예담 담당, Python)

## Backend
- Python 3.10
- FastAPI · Uvicorn
- Pydantic v2 / pydantic-settings
- RESTful API
- Multipart File Upload (PDF, DOCX)
- OpenAPI / Public API Integration (httpx)

## Database
- PostgreSQL (운영) / SQLite (개발)
- SQLAlchemy 2.0 ORM

## Security
- OAuth 2.0 Authorization Code Flow (Kakao)
- JWT (python-jose) — Access / Refresh Token
- API Key Encryption
- CORS · 입력값 검증(pydantic)

## AI 연동 (in-process, 호출만)
- vikira RAG 파이프라인 함수 호출 (ingestion · search · report)
- 직접 구현 제외: VLM · LLM · LangGraph · BGE-m3 · ChromaDB · BM25 · Cross-Encoder

## Infrastructure
- UUID Session Management
- Environment Variables (.env)
- Git / GitHub

## Tools
- VS Code / PyCharm
- Postman
- Docker

## Quality
- Ruff · Black · pytest
