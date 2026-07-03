# SpecKit — Backend (김예담 담당, Python)

## 역할
FastAPI 기반으로 **사용자 인증 · 문서(업로드·조회·삭제) 통신 · 공공데이터 API(카탈로그·동적 호출) · RDBMS 메타/세션 UUID**를 담당한다. (확정 담당 기능 10개 — 아래 F1~F10)
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

## 담당 기능 (확정 10개 · F1~F10)

> 담당자(김예담)가 구현해야 하는 확정 기능 목록. 각 항목은 진행도 추적의 기준(§진행도)이 된다.

### A. 인증 (Auth)
- **F1. 인가 코드 기반 사용자 식별 및 DB 동기화 로직**
  - 카카오 OAuth2 Authorization Code → 사용자 정보 조회 → 최초 저장/기존 동기화(upsert)
- **F3. 무상태(Stateless) JWT Access/Refresh 토큰 발급 API**
- **F4. 백그라운드 JWT 자동 갱신 (Silent Refresh)** — Refresh 토큰으로 Access 재발급

### B. 문서 통신 (Documents)
- **F2. 비정형 사내 문서(PDF·DOCX) 멀티 업로드·조회·삭제 통신 로직**
  - Multipart **멀티 업로드** + 검증(`.pdf`/`.docx`) + 저장 → `ingest_file` 호출(vikira 파이프라인)
  - 문서 **목록 조회 · 단건 조회 · 삭제**

### C. 보안 (Security)
- **F5. API Key 소스코드 분리 및 RDBMS 암호화**
  - `.env` 환경변수 분리 + **DB 저장 시 암호화** · 응답 비노출

### D. 공공데이터 (Public Data)
- **F6. 공공데이터 오픈 API 카탈로그 메타 등록 로직**
  - API 카탈로그(엔드포인트·파라미터 스펙·기관·도메인) 메타 등록/관리
- **F9. 공공 API 동적 파라미터(엔티티) 매핑 및 조립**
  - 질의 엔티티 → 카탈로그 파라미터 매핑 → 요청 조립
- **F10. 외부 공공 API On-demand 실시간 직접 호출**
  - 실시간 호출(httpx) · 응답 파싱 (필요 시 vikira 서비스로 전달)

### E. RDBMS 메타 / 세션 (Metadata / Session)
- **F7. RDBMS 메타데이터 동기화 (PostgreSQL)**
  - 사용자·문서·공공데이터·세션 메타를 SQLAlchemy 로 저장/동기화 (CRUD·트랜잭션)
- **F8. [캐시 버그 차단] 매 쿼리 난수 세션 UUID 생성**
  - 검색 요청마다 **난수 세션 UUID 발급** → 동일 결과 반복(캐시) 오류 차단
  - (※ 세션 *이력 로깅/복원*은 본 범위에 포함하지 않음 — UUID 생성까지)

> **모델(PostgreSQL)**: `User` · `RefreshToken` · `PublicApiCatalog` · (세션 UUID) + vikira `KnowledgeDocument`·`GeneratedReport` 연계.

---

## 통합 지점 (in-process, REST 아님)
| 목적 | 호출 대상 |
| --- | --- |
| 업로드 후 문서 분석 | `app.services.ingestion.ingest_file(path, db, domain, title)` |
| 통합 검색 | vikira `POST /search` (또는 `services.search_service`) |
| 보고서 생성 | vikira `POST /reports` (또는 report 서비스) |

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
