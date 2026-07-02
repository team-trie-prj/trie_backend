# API 명세서 — 김예담 담당 (Python / FastAPI)

- **Base URL**: `http://<host>:8000` · prefix `/api/v1`
- **형식**: JSON (업로드는 `multipart/form-data`), **snake_case**
- **인증**: 보호 API 는 `Authorization: Bearer <access_token>`
- **에러**: FastAPI 표준 `{ "detail": "<메시지>" }`
- **도메인 enum**: `road | safety | traffic | etc`
- **자동 문서**: `/docs` · `/openapi.json`

> vikira 담당(수집/검색/보고서)은 [API.md](API.md) 참조. 본 문서는 **김예담 확정 담당 기능 F1~F10** ([backend-speckit.md](backend-speckit.md)).
> **구현 상태**: ✅ 구현·검증 완료 · 🟡 부분 · 📝 예정

| 기능 | 엔드포인트 | 상태 |
| --- | --- | --- |
| F1·F3 로그인 | `POST /auth/kakao` | ✅ |
| F4 Silent Refresh | `POST /auth/refresh` | ✅ |
| 로그아웃 | `POST /auth/logout` | ✅ |
| F2 문서 멀티 업로드 | `POST /documents` | ✅ |
| F2 문서 목록 | `GET /documents` | ✅ |
| F2 문서 단건 | `GET /documents/{id}` | ✅ |
| F2 문서 삭제 | `DELETE /documents/{id}` | ✅ |
| F5 API Key 등록 | `POST /api-keys` | ✅ |
| F5 API Key 목록 | `GET /api-keys` | ✅ |
| F5 API Key 삭제 | `DELETE /api-keys/{name}` | ✅ |
| F6 공공 카탈로그 등록 | `POST /public-data/catalog` | 📝 |
| F6 공공 카탈로그 목록/단건/삭제 | `GET·DELETE /public-data/catalog[/{id}]` | 📝 |
| F9·F10 공공 On-demand 호출 | `POST /public-data/{catalog_id}/fetch` | 📝 |
| F8 세션 UUID 발급 | `POST /sessions` | 📝 |

> F7(RDBMS 메타데이터 동기화)은 별도 엔드포인트가 아니라 F2 업로드/삭제 시 업로더·시각·도메인 메타를 PostgreSQL 에 동기화하는 **횡단 기능**이다.

---

## 1. 인증 (auth) — F1·F3·F4

### ✅ POST `/api/v1/auth/kakao`
카카오 인가 코드 → 사용자 동기화 → JWT 발급.
**요청**: `{ "code": "...", "redirect_uri": "..." }`
**200**: `{ "access_token","refresh_token","token_type":"bearer","expires_in":3600, "user":{ "id","name","email","provider" } }`
**에러**: `401`(코드 무효) · `422`(검증) · `502`(카카오 통신)

### ✅ POST `/api/v1/auth/refresh`
**요청**: `{ "refresh_token": "..." }` → **200**: `{ "access_token","token_type","expires_in" }` · **에러** `401`

### ✅ POST `/api/v1/auth/logout`
`Authorization: Bearer` → **200**: `{ "detail": "logged out" }`

---

## 2. 문서 (documents) — F2 (+ F7 메타 동기화)

### ✅ POST `/api/v1/documents`  🔒
비정형 문서 **멀티 업로드**. 파일별 검증(`.pdf`/`.docx`) → 저장 → `ingest_file`(vikira) 호출 → **업로더·업로드시각·원본파일명 메타를 RDBMS 동기화(F7)**.

**요청** `multipart/form-data`
| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `files` | file[] | ✔ | `.pdf` / `.docx` (다중) |
| `domain` | string | ✖ | `road|safety|traffic|etc` (기본 `etc`) |

**200** — 파일별 성공/실패 분리
```json
{
  "items": [
    { "document_id": 1, "title": "도로 유지보수 지침서", "doc_type": "pdf", "domain": "road",
      "status": "indexed", "chunk_count": 18, "uploaded_by": 1, "original_filename": "지침서.pdf" }
  ],
  "failed": [ { "filename": "bad.zip", "detail": "지원하지 않는 형식: .zip" } ]
}
```
**에러**: `401`(미인증) · `413`(용량) · `422`(검증)

### ✅ GET `/api/v1/documents`
목록(최신순). **응답** `DocumentOut[]` (id·title·doc_type·domain·status·chunk_count·created_at·meta)

### ✅ GET `/api/v1/documents/{document_id}`
단건. **에러** `404`

### ✅ DELETE `/api/v1/documents/{document_id}`  🔒
문서 삭제: **저장 파일 + ChromaDB 벡터(`delete_by_document`) + RDBMS 행(청크 cascade)** 동기 제거.
**200**: `{ "detail": "deleted", "document_id": 1 }` · **에러** `401` · `404`

> `POST /documents/ingest`(단건)는 vikira 파이프라인 검증용 하니스([API.md](API.md) §2). 프로덕션 통신은 위 `POST /documents`.

---

## 3. API Key (api-keys) — F5  🔒
API Key 를 **소스코드에서 분리**하고 **RDBMS 에 암호화(Fernet)** 저장. 평문은 **응답에 절대 노출하지 않음**(마스킹).

### ✅ POST `/api/v1/api-keys`
등록/갱신(upsert).
**요청**: `{ "name": "data_go_kr", "provider": "data.go.kr", "secret": "실제키", "description": "공공데이터 서비스키" }`
**200** (마스킹): `{ "name":"data_go_kr","provider":"data.go.kr","secret_preview":"실제••••","description":"...","updated_at":"..." }`

### ✅ GET `/api/v1/api-keys`
목록(마스킹). 평문 미포함.

### ✅ DELETE `/api/v1/api-keys/{name}`
삭제. **200**: `{ "detail":"deleted","name":"data_go_kr" }` · **에러** `404`

> 복호화된 평문은 **서버 내부 서비스**(`api_key_service.get_secret`)에서만 사용된다(예: F10 공공 API 호출).

---

## 4. 공공데이터 (public-data) — F6·F9·F10  📝(예정)

### 📝 카탈로그 메타 등록 (F6)
- `POST /api/v1/public-data/catalog` — 등록: `{ name, provider, domain, endpoint, params_spec:[{name,type,required,default}], description }`
- `GET /api/v1/public-data/catalog` · `GET .../{id}` · `DELETE .../{id}`

### 📝 On-demand 실시간 호출 (F9 매핑·조립 + F10 호출)
- `POST /api/v1/public-data/{catalog_id}/fetch`
  - 요청: `{ "entities": { ... } }` → 카탈로그 `params_spec` 로 **파라미터 매핑·조립(F9)** → 외부 API **실시간 호출(F10, httpx)** → JSON 파싱 반환
  - 응답: `{ "source", "api_name", "items":[...] }`
  - 서비스 키는 §3 `api_key_service` 에서 복호화해 사용.

---

## 5. 세션 UUID (sessions) — F8  📝(예정)
- `POST /api/v1/sessions` — **매 쿼리 난수 세션 UUID 발급**(캐시 버그 차단). 응답 `{ "session_uuid": "..." }`.
- ※ 세션 *이력 로깅/복원*은 본 범위 밖(UUID 생성까지).

---

## 데이터 모델
[entity.md](entity.md) 참조. 김예담 모델: **User · RefreshToken · ApiKey**(암호화) · **PublicApiCatalog**(예정) · 세션 UUID. (SQLAlchemy, 물리 컬럼 snake_case)
