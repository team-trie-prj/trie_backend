# ABC_BACK API 명세서 (김예담 담당)

> 노션 붙여넣기/Import 용. 실제 구현 동작 기준(F1~F10). vikira 담당(검색·보고서·수집 `/api/v1/*`)은 별도.

## 공통 규약

- **Base URL**: `http://<host>:8000`
- **경로**: 김예담 API 는 기능별 루트 (`/auth` `/documents` `/api-keys` `/public-data` `/sessions`)
- **요청/응답**: JSON, **snake_case** (업로드만 `multipart/form-data`)
- **인증**: 보호 API 는 `Authorization: Bearer {accessToken}`

### 응답 형식 (공통 Envelope)

모든 응답(성공·실패)은 아래 envelope 로 감싼다.

```json
{ "success": true, "code": "OK", "message": "요청 성공", "data": { } }
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `success` | boolean | 처리 성공 여부 |
| `code` | string | 결과 코드 — HTTP 상태명(`OK`·`BAD_REQUEST`·`UNAUTHORIZED`·`NOT_FOUND`·`CONFLICT`·`UNPROCESSABLE_ENTITY`·`BAD_GATEWAY`·`GATEWAY_TIMEOUT`·`INTERNAL_SERVER_ERROR` …) |
| `message` | string | 사람이 읽는 메시지 |
| `data` | object\|array\|null | 실제 페이로드 (실패 시 `null`, 검증 실패 시 오류 상세 배열) |

**실패 응답 예시**

```json
{ "success": false, "code": "UNAUTHORIZED", "message": "유효하지 않은 리프레시 토큰입니다.", "data": null }
```

- 입력 검증 실패는 `422 UNPROCESSABLE_ENTITY` 이며 `data` 에 필드별 오류 배열이 담긴다.
- 도메인 enum: `road | safety | traffic | etc`

### 응답 표기 범례

- ✅ **성공** (2xx) · ❌ **실패** (4xx / 5xx) · ⚪ **해당 없음** (이 엔드포인트에서는 발생하지 않음)

---

# 1. 인증 (Auth)

## `POST /auth/kakao` — 카카오 로그인 (F1·F3)

**인증**: 불필요

**Request Headers**

- `Content-Type: application/json`
- `Accept: application/json`

**Request Body**

```json
{ "code": "카카오 인가 코드", "redirect_uri": "http://localhost:5173/oauth/kakao/callback" }
```

**Response**

`200 OK` · ✅ **성공**

```json
{
  "success": true, "code": "OK", "message": "로그인 성공",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": { "id": 1, "name": "홍길동", "email": null, "provider": "kakao" }
  }
}
```

`401 Unauthorized` · ❌ **실패** — 인가 코드 무효/만료/자격 오류

```json
{ "success": false, "code": "UNAUTHORIZED", "message": "카카오 인가 코드 검증 실패 — KOE010: Bad client credentials", "data": null }
```

`422 Unprocessable Entity` · ❌ **실패** — 입력 검증 실패(code 누락 등)

```json
{ "success": false, "code": "UNPROCESSABLE_ENTITY", "message": "입력값이 올바르지 않습니다.", "data": [ { "type": "missing", "loc": ["body", "code"], "msg": "Field required" } ] }
```

`502 Bad Gateway` · ❌ **실패** — 카카오 사용자 정보 조회 실패

```json
{ "success": false, "code": "BAD_GATEWAY", "message": "카카오 사용자 정보 조회 실패 — ...", "data": null }
```

`404 Not Found` · ⚪ **해당 없음** (로그인 시 사용자 자동 생성)
`409 Conflict` · ⚪ **해당 없음**
`500 Internal Server Error` · ❌ **실패**

---

## `POST /auth/refresh` — 토큰 재발급 / Silent Refresh (F4)

**인증**: 불필요 (refresh_token 을 Body 로 전달)

**Request Headers**

- `Content-Type: application/json`
- `Accept: application/json`

**Request Body**

```json
{ "refresh_token": "eyJhbGciOiJIUzI1NiJ9..." }
```

**Response**

`200 OK` · ✅ **성공**

```json
{
  "success": true, "code": "OK", "message": "토큰 재발급",
  "data": { "access_token": "eyJhbGciOiJIUzI1NiJ9...", "token_type": "bearer", "expires_in": 3600 }
}
```

`401 Unauthorized` · ❌ **실패** — 만료/무효/폐기됨

```json
{ "success": false, "code": "UNAUTHORIZED", "message": "폐기되었거나 알 수 없는 리프레시 토큰입니다.", "data": null }
```

`422 Unprocessable Entity` · ❌ **실패** — refresh_token 누락
`404 / 409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

## `POST /auth/logout` — 로그아웃

**인증**: 필요

**Request Headers**

- `Accept: application/json`
- `Authorization: Bearer {accessToken}`

**Request Body**: 없음

**Response**

`200 OK` · ✅ **성공**

```json
{ "success": true, "code": "OK", "message": "logged out", "data": null }
```

`401 Unauthorized` · ❌ **실패** — 인증 정보 없음/토큰 무효

```json
{ "success": false, "code": "UNAUTHORIZED", "message": "인증 정보가 없습니다.", "data": null }
```

`404 / 409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

# 2. 문서 통신 (Documents, F2 · 메타 동기화 F7)

## `POST /documents` — 멀티 업로드

**인증**: 필요

**Request Headers**

- `Content-Type: multipart/form-data`
- `Accept: application/json`
- `Authorization: Bearer {accessToken}`

**Request Body** (`multipart/form-data`)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `files` | file[] | ✔ | `.pdf` / `.docx` (다중) |
| `domain` | string | ✖ | `road|safety|traffic|etc` (기본 `etc`) |

**Response**

`200 OK` · ✅ **성공** — 파일별 성공(`items`)/실패(`failed`) 분리

```json
{
  "success": true, "code": "OK", "message": "업로드 완료",
  "data": {
    "items": [
      { "document_id": 1, "title": "도로 유지보수 지침서", "doc_type": "pdf",
        "domain": "road", "status": "indexed", "chunk_count": 18,
        "uploaded_by": 1, "original_filename": "지침서.pdf" }
    ],
    "failed": [ { "filename": "big.zip", "detail": "지원하지 않는 형식: .zip" } ]
  }
}
```

> 미지원 형식·파일당 용량 초과(기본 50MB)는 요청 전체 실패가 아니라 해당 파일만 `data.failed` 로 분리(부분 성공).

`401 Unauthorized` · ❌ **실패**

```json
{ "success": false, "code": "UNAUTHORIZED", "message": "인증 정보가 없습니다.", "data": null }
```

`422 Unprocessable Entity` · ❌ **실패** — `files` 누락
`404 / 409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

## `GET /documents` — 문서 목록

**인증**: 불필요 · **Query**: `domain`(선택) · **Headers**: `Accept: application/json`

**Response**

`200 OK` · ✅ **성공**

```json
{
  "success": true, "code": "OK", "message": "요청 성공",
  "data": [
    { "id": 1, "title": "도로 유지보수 지침서", "doc_type": "pdf", "domain": "road",
      "status": "indexed", "char_count": 12034, "chunk_count": 18, "created_at": "2026-07-03T09:12:33" }
  ]
}
```

`401 / 404 / 409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

## `GET /documents/{document_id}` — 문서 단건

**인증**: 불필요 · **Headers**: `Accept: application/json`

**Response**

`200 OK` · ✅ **성공**

```json
{
  "success": true, "code": "OK", "message": "요청 성공",
  "data": { "id": 1, "title": "도로 유지보수 지침서", "doc_type": "pdf", "domain": "road",
            "status": "indexed", "char_count": 12034, "chunk_count": 18, "created_at": "2026-07-03T09:12:33" }
}
```

`404 Not Found` · ❌ **실패** — 문서 없음

```json
{ "success": false, "code": "NOT_FOUND", "message": "문서를 찾을 수 없습니다.", "data": null }
```

`401 / 409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

## `DELETE /documents/{document_id}` — 문서 삭제

**인증**: 필요 · **Headers**: `Authorization: Bearer {accessToken}` · **Body**: 없음

**Response**

`200 OK` · ✅ **성공** — 저장 파일 + ChromaDB 벡터 + DB 행 동기 삭제

```json
{ "success": true, "code": "OK", "message": "deleted", "data": { "document_id": 1 } }
```

`401 Unauthorized` · ❌ **실패**
`404 Not Found` · ❌ **실패**

```json
{ "success": false, "code": "NOT_FOUND", "message": "문서를 찾을 수 없습니다.", "data": null }
```

`409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

# 3. API Key (Security, F5)

## `POST /api-keys` — API Key 등록/갱신

**인증**: 필요 · 평문은 RDBMS 암호화 저장, 응답엔 마스킹만.

**Request Headers**

- `Content-Type: application/json`
- `Accept: application/json`
- `Authorization: Bearer {accessToken}`

**Request Body**

```json
{ "name": "data_go_kr", "provider": "data.go.kr", "secret": "실제_서비스키", "description": "공공데이터 서비스키" }
```

**Response**

`200 OK` · ✅ **성공** — 등록/갱신(upsert), 평문 마스킹

```json
{
  "success": true, "code": "OK", "message": "등록 완료",
  "data": { "name": "data_go_kr", "provider": "data.go.kr", "secret_preview": "실제••••", "description": "공공데이터 서비스키", "updated_at": "2026-07-03T10:00:00" }
}
```

`401 Unauthorized` · ❌ **실패** · `422 Unprocessable Entity` · ❌ **실패**(name/secret 누락)
`404 / 409` · ⚪ **해당 없음**(upsert) · `500` · ❌ **실패**

---

## `GET /api-keys` — API Key 목록

**인증**: 필요 · 평문 미포함(마스킹).

**Request Headers**: `Accept: application/json` · `Authorization: Bearer {accessToken}`

**Response**

`200 OK` · ✅ **성공**

```json
{
  "success": true, "code": "OK", "message": "요청 성공",
  "data": [ { "name": "data_go_kr", "provider": "data.go.kr", "secret_preview": "실제••••", "description": "...", "updated_at": "2026-07-03T10:00:00" } ]
}
```

`401 Unauthorized` · ❌ **실패** · `404 / 409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

## `DELETE /api-keys/{name}` — API Key 삭제

**인증**: 필요 · **Headers**: `Authorization: Bearer {accessToken}`

**Response**

`200 OK` · ✅ **성공**

```json
{ "success": true, "code": "OK", "message": "deleted", "data": { "name": "data_go_kr" } }
```

`401 Unauthorized` · ❌ **실패**
`404 Not Found` · ❌ **실패**

```json
{ "success": false, "code": "NOT_FOUND", "message": "API Key 를 찾을 수 없습니다.", "data": null }
```

`409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

# 4. 공공데이터 (Public Data, F6·F9·F10)

## `POST /public-data/catalog` — 카탈로그 등록 (F6)

**인증**: 필요

**Request Headers**

- `Content-Type: application/json`
- `Accept: application/json`
- `Authorization: Bearer {accessToken}`

**Request Body**

```json
{
  "name": "에어코리아 시도별 실시간 대기오염도",
  "provider": "한국환경공단",
  "domain": "traffic",
  "endpoint": "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty",
  "http_method": "GET",
  "params_spec": [
    { "name": "sidoName", "type": "str", "required": true, "map_from": "region" },
    { "name": "numOfRows", "type": "int", "default": 5 },
    { "name": "returnType", "type": "str", "default": "json" }
  ],
  "api_key_name": "data_go_kr",
  "api_key_param": "serviceKey",
  "description": "시도별 실시간 PM10/PM2.5"
}
```

**Response**

`200 OK` · ✅ **성공**

```json
{
  "success": true, "code": "OK", "message": "등록 완료",
  "data": {
    "id": 1, "name": "에어코리아 시도별 실시간 대기오염도", "provider": "한국환경공단",
    "domain": "traffic", "endpoint": "http://apis.data.go.kr/...", "http_method": "GET",
    "params_spec": [ { "name": "sidoName", "type": "str", "required": true, "default": null, "map_from": "region" } ],
    "api_key_name": "data_go_kr", "api_key_param": "serviceKey",
    "description": "시도별 실시간 PM10/PM2.5", "created_at": "2026-07-03T10:00:00"
  }
}
```

`409 Conflict` · ❌ **실패** — 이름 중복

```json
{ "success": false, "code": "CONFLICT", "message": "이미 등록된 카탈로그: 에어코리아 시도별 실시간 대기오염도", "data": null }
```

`401 Unauthorized` · ❌ **실패** · `422` · ❌ **실패**(name/endpoint 누락) · `404` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

## `GET /public-data/catalog` — 카탈로그 목록

**인증**: 불필요 · **Query**: `domain`(선택)

**Response**

`200 OK` · ✅ **성공** — `data` 는 카탈로그 배열(등록 응답 `data` 구조)

`401 / 404 / 409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

## `GET /public-data/catalog/{catalog_id}` — 카탈로그 단건

**인증**: 불필요

**Response**

`200 OK` · ✅ **성공** — `data` 는 카탈로그 객체

`404 Not Found` · ❌ **실패**

```json
{ "success": false, "code": "NOT_FOUND", "message": "카탈로그를 찾을 수 없습니다.", "data": null }
```

`401 / 409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

## `DELETE /public-data/catalog/{catalog_id}` — 카탈로그 삭제

**인증**: 필요 · **Headers**: `Authorization: Bearer {accessToken}`

**Response**

`200 OK` · ✅ **성공**

```json
{ "success": true, "code": "OK", "message": "deleted", "data": { "catalog_id": 1 } }
```

`401 Unauthorized` · ❌ **실패** · `404 Not Found` · ❌ **실패** · `409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

## `POST /public-data/{catalog_id}/fetch` — 실시간 호출 (F9 매핑 + F10 호출)

**인증**: 필요 · 엔티티 → 파라미터 매핑·조립 후 외부 공공 API 실호출. 서비스 키는 복호화 주입, 응답엔 마스킹.

**Request Headers**

- `Content-Type: application/json`
- `Accept: application/json`
- `Authorization: Bearer {accessToken}`

**Request Body**

```json
{ "entities": { "region": "대전" } }
```

**Response**

`200 OK` · ✅ **성공**

```json
{
  "success": true, "code": "OK", "message": "요청 성공",
  "data": {
    "catalog_id": 1, "api_name": "에어코리아 시도별 실시간 대기오염도", "provider": "한국환경공단",
    "endpoint": "http://apis.data.go.kr/...",
    "assembled_params": { "sidoName": "대전", "numOfRows": 5, "returnType": "json", "serviceKey": "실제••••" },
    "status_code": 200,
    "items": [ { "stationName": "읍내동", "pm10Value": "5", "pm25Value": "2", "dataTime": "2026-07-03 10:00" } ],
    "data": null, "elapsed_sec": 4.55
  }
}
```

`401 Unauthorized` · ❌ **실패**
`404 Not Found` · ❌ **실패** — 카탈로그 없음
`422 Unprocessable Entity` · ❌ **실패** — 필수 파라미터 누락/타입 변환 실패

```json
{ "success": false, "code": "UNPROCESSABLE_ENTITY", "message": "필수 파라미터 누락: sidoName", "data": null }
```

`502 Bad Gateway` · ❌ **실패** — 외부 공공 API 4xx/5xx·통신 실패

```json
{ "success": false, "code": "BAD_GATEWAY", "message": "공공 API 오류(HTTP 500): ...", "data": null }
```

`504 Gateway Timeout` · ❌ **실패** — 외부 공공 API 응답 지연

```json
{ "success": false, "code": "GATEWAY_TIMEOUT", "message": "공공 API 응답 지연: 에어코리아 시도별 실시간 대기오염도", "data": null }
```

`409` · ⚪ **해당 없음** · `500` · ❌ **실패**

---

# 5. 세션 UUID (Session, F8)

## `POST /sessions` — 세션 UUID 발급

**인증**: 불필요 · 매 호출 난수 UUID4 + `Cache-Control: no-store` (캐시 버그 차단).

**Request Headers**: `Accept: application/json` · **Body**: 없음

**Response**

`200 OK` · ✅ **성공** (응답 헤더 `Cache-Control: no-store, no-cache, must-revalidate`)

```json
{
  "success": true, "code": "OK", "message": "요청 성공",
  "data": { "session_uuid": "9f1c2d3e-1a2b-4c3d-8e9f-0a1b2c3d4e5f", "issued_at": "2026-07-03T10:00:00" }
}
```

`401 / 404 / 409` · ⚪ **해당 없음** · `500` · ❌ **실패**
