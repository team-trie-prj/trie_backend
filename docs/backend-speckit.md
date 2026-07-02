# SpecKit — Backend (김예담 담당, Python)

## 역할
FastAPI 기반으로 **사용자 인증 · 문서 업로드 통신 · 공공데이터 API 연동 · 메타/세션 관리**를 담당한다.
AI 추론(RAG)은 **vikira 파이프라인을 in-process로 호출**하며 직접 구현하지 않는다. (→ [backend-context.md](backend-context.md))

---

## 개발 환경
| 구분 | 스택 |
| --- | --- |
| Language | Python 3.10 |
| Framework | FastAPI · Uvicorn |
| ORM / DB | SQLAlchemy 2.0 · PostgreSQL(운영) / SQLite(개발) |
| Auth | OAuth2 Authorization Code(카카오) · JWT(python-jose) Access/Refresh |
| HTTP Client | httpx (공공 Open API) |
| Validation / Config | pydantic v2 · pydantic-settings(.env) |
| API Docs | Swagger/OpenAPI (FastAPI 내장 `/docs`) |
| Quality | Ruff · Black · pytest |

> **requirements.txt 추가 필요(김예담 파트)**: `python-jose[cryptography]`, `httpx`, (선택) `authlib`, `passlib[bcrypt]`.
> 기존 `fastapi·uvicorn·sqlalchemy·psycopg2·pydantic`은 vikira requirements 에 이미 포함.

---

## 담당 기능

### 1. 사용자 인증
- 카카오 OAuth2 **Authorization Code** 로그인
- 사용자 정보 조회 → **최초 로그인 시 DB 저장, 기존 사용자 동기화**
- **JWT** Access/Refresh 발급, **Stateless** 인증, Refresh 재발급(Silent Refresh)

### 2. 문서 업로드 통신 (프로덕션)
- Multipart 멀티 업로드, 파일 검증(`.pdf`/`.docx`), 저장 경로 관리
- 저장 후 `app.services.ingestion.ingest_file(...)` 호출로 **vikira 수집 파이프라인 트리거**
- (vikira의 `/documents/ingest`는 파이프라인 단독 검증용 하니스 — 프로덕션 통신은 본 파트)

### 3. PostgreSQL 관리
- 모델: **User · RefreshToken · SearchSession · PublicDataMetadata** (+ vikira `KnowledgeDocument`·`GeneratedReport` 연계)
- CRUD · 트랜잭션 · SQLAlchemy 세션(`get_db`)

### 4. 공공데이터 API
- Open API 호출(httpx) · **파라미터 조립** · JSON 응답 파싱
- 결과를 검색/보고서 컨텍스트로 제공(필요 시 vikira 서비스로 전달)

### 5. 메타데이터 관리
- 저장 항목: 문서 ID · 파일명 · 업로드 시간 · 도메인 · 작성자 · **검색 세션 UUID**

### 6. API Key 관리
- `.env` 환경변수 분리 · 저장 시 암호화 · 서버 내부에서만 사용(응답 비노출)

### 7. UUID 세션 관리
- 검색 요청마다 **UUID 생성** · 동일 결과 캐시 문제 방지 · 세션 이력 로깅/복원

---

## 통합 지점 (in-process, REST 아님)
| 목적 | 호출 대상 |
| --- | --- |
| 업로드 후 문서 분석 | `app.services.ingestion.ingest_file(path, db, domain, title)` |
| 통합 검색 | vikira `POST /api/v1/search` (또는 `services.search_service`) |
| 보고서 생성 | vikira `POST /api/v1/reports` (또는 report 서비스) |

---

## 예외 처리 (FastAPI 표준)
- 형식: `{ "detail": "<메시지>" }` (`HTTPException`)
- 주요 코드: `200` · `401`(인증 실패/토큰 만료) · `404`(없음) · `413`(용량 초과) · `415`(미지원 형식) · `422`(검증 실패) · `500`(처리 오류) · `502/504`(공공 API 오류/타임아웃)
- 처리 대상 예외: JWT 만료, 인증 실패, 파일 업로드 실패, DB 오류, 공공 API 타임아웃

## 보안
OAuth2 · JWT · API Key 암호화 · CORS(허용 오리진 화이트리스트) · 입력값 검증(pydantic)

---

## 담당 범위 제외 (vikira / AI — 호출만)
`VLM` · `LLM(Gemini)` · `LangGraph` · `BGE-m3` · `ChromaDB` · `BM25` · `Cross-Encoder` · `Semantic Chunking` · `Intent 분석` · `Query Routing` · `보고서 프롬프트 생성`
→ 위 기능은 **호출만** 하며 직접 구현하지 않는다.
