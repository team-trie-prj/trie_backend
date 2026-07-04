# Backend Context — Python 모노레포

이 저장소(`trie_backend`)는 **단일 FastAPI 애플리케이션(모노레포)**이다.
별도의 AI 서버는 없으며, RAG/AI 파이프라인과 백엔드(인증·업로드·공공데이터·세션)가 **같은 프로세스** 안에 공존한다.

> ⚠️ 이전 설계(Spring Boot 백엔드 ↔ 별도 AI 서버 REST 분리)는 **폐기**되었다. 지금은 전부 Python/FastAPI 단일 앱이다.

## 소유권 분리 (같은 코드베이스, 모듈 경계)
| 담당 | 범위 | 주요 위치 |
| --- | --- | --- |
| **vikira** | RAG/AI 파이프라인 (수집·멀티모달·에이전트·검색·보고서) | `app/pipeline`, `app/vectorstore`, `app/llm`, `app/agent`, `app/search`, `app/services/{ingestion,multimodal,search_service}`, `app/api/{documents(ingest),search,reports}` |
| **김예담(본인)** | 인증·업로드 통신·공공데이터·DB 동기화·세션/이력·API Key | `app/api/{auth,public_data,sessions}`, `app/services/*`, `app/models/{user,refresh_token,search_session,public_data_metadata}` |

## 통합 방식 = in-process 함수 호출 (NOT REST)
- 업로드 통신 → `app.services.ingestion.ingest_file(path, db, domain, title)` **직접 호출**.
- 통합 검색/보고서 → vikira의 `POST /api/v1/search`, `POST /api/v1/reports`(또는 `search_service`/`report_service`) **재사용**.
- 즉, 백엔드는 AI 서버를 HTTP로 호출하지 않는다. 같은 앱의 서비스 함수를 호출한다.

## 계층 구조 (실제 `app/`)
```
app/
  main.py          FastAPI 진입점 (라우터 등록)
  config.py        pydantic-settings (.env)
  database.py      SQLAlchemy 엔진 / 세션(get_db) / Base
  models/          ORM: KnowledgeDocument·DocumentChunk·VisualResource·GeneratedReport
                        (+ 김예담 추가: User·RefreshToken·SearchSession·PublicDataMetadata)
  schemas/         pydantic 요청/응답 스키마
  api/             라우터: documents·search·reports  (+ 김예담: auth·public_data·sessions)
  services/        비즈니스 로직: ingestion·multimodal·search_service  (+ 김예담: auth·public_data)
  pipeline/ vectorstore/ llm/ agent/ search/   ← vikira RAG 내부 (직접 구현 안 함)
```

## 데이터베이스
- **SQLAlchemy 2.0**. 개발은 SQLite(`sqlite:///./data/trie.db`) 무설정 구동, 운영은 `DATABASE_URL`만 교체해 PostgreSQL.
- `get_db()` 의존성 주입, dev 는 `Base.metadata.create_all`(시작 시). 운영은 Alembic 마이그레이션 권장.

## 원칙
- AI 추론은 직접 구현하지 않고 **vikira 서비스 호출**.
- FastAPI 규약 준수: **김예담 API 는 기능별 루트**(`/auth` `/documents` `/api-keys` `/public-data` `/sessions`), **vikira API 는 `/api/v1` 유지** · snake_case JSON · 에러 `{ "detail": ... }`.
- 계층 경계 유지, 유지보수성 우선.

## 관련 문서
[requirements.md](requirements.md) · [backend-speckit.md](backend-speckit.md) · [api-spec.md](api-spec.md) · [entity.md](entity.md) · [API.md](API.md)(vikira)
