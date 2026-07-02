# API 명세서 — 김예담 담당 (Python / FastAPI)

- **Base URL**: `http://<host>:8000` · prefix `/api/v1`
- **형식**: JSON (업로드는 `multipart/form-data`), **snake_case**
- **인증**: 보호 API 는 `Authorization: Bearer <access_token>`
- **에러**: FastAPI 표준 `{ "detail": "<메시지>" }`
- **도메인 enum**: `road | safety | traffic | etc`
- **자동 문서**: `/docs` · `/openapi.json`

> vikira 담당(수집/검색/보고서)은 [API.md](API.md) 참조. **본 문서는 인증·업로드·공공데이터·세션 담당 API**.

---

## 1. 인증 (auth)

### POST `/api/v1/auth/kakao`
카카오 인가 코드로 로그인 → 사용자 동기화 → JWT 발급.

**요청** `application/json`
```json
{ "code": "authorization_code", "redirect_uri": "https://app.example.com/oauth/callback" }
```
**응답 200**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { "id": 1, "name": "홍길동", "email": "user@email.com", "provider": "kakao" }
}
```
**에러**: `401`(인가 코드 무효/만료) · `422`(요청 검증) · `502`(카카오 통신 오류)

### POST `/api/v1/auth/refresh`
**요청**: `{ "refresh_token": "..." }`
**응답 200**: `{ "access_token": "...", "token_type": "bearer", "expires_in": 3600 }`
**에러**: `401`(Refresh 무효/만료)

### POST `/api/v1/auth/logout`
**Header**: `Authorization: Bearer` · **응답 200**: `{ "detail": "logged out" }`

---

## 2. 문서 업로드 (documents) — 프로덕션 통신
### POST `/api/v1/documents`
Multipart 멀티 업로드. 검증·저장 후 `ingest_file` 호출로 vikira 수집 파이프라인 실행.

**요청** `multipart/form-data`
| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `files` | file[] | ✔ | `.pdf` / `.docx` |
| `domain` | string | ✖ | 기본 `etc` |

**응답 200**
```json
{ "items": [ { "document_id": 1, "title": "도로 유지보수 지침서", "domain": "road", "status": "indexed" } ] }
```
**에러**: `415`(미지원 형식) · `413`(용량 초과) · `500`(수집 실패)

> 조회 `GET /api/v1/documents`, `GET /api/v1/documents/{id}` 는 vikira 구현([API.md](API.md) §2) 공유.

---

## 3. 공공데이터 (public-data)
### GET `/api/v1/public-data`
공공 Open API 호출 → 파라미터 조립 → JSON 파싱.

**Query**: `type`(필수) · `keyword`(선택) · `domain`(선택)
**응답 200**
```json
{ "source": "data.go.kr", "api_name": "노면상태별 사고 통계", "items": [ { "region": "대전", "count": 340 } ] }
```
**에러**: `502`(호출 실패) · `504`(타임아웃)

---

## 4. 세션 / 이력 (sessions)
### GET `/api/v1/sessions`
검색 세션 이력 목록(최신순).
```json
[ { "session_id": "8f3c...", "query": "포트홀 보수 절차", "domain": "road", "created_at": "2026-07-01T10:20:00" } ]
```

### GET `/api/v1/sessions/{session_id}`
세션 복원(질의/도메인/결과/보고서 연계).
**에러**: `404`(없음)

---

## 데이터 모델
[entity.md](entity.md) 참조. 김예담 신규 모델: **User · RefreshToken · SearchSession · PublicDataMetadata** (Python/SQLAlchemy, 물리 컬럼 snake_case).
