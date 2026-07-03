# trie_backend API 명세서

- **버전**: 0.1.0
- **Base URL**: `http://<host>:8000` · API prefix `/api/v1`
- **형식**: 요청/응답 JSON (파일 업로드는 `multipart/form-data`)
- **자동 문서**: `/docs` (Swagger UI) · `/redoc` · `/openapi.json` (머신 스펙은 [openapi.json](openapi.json))

> 본 명세서는 **vikira 담당 RAG/AI 파이프라인** API를 기술한다.
> 인증(카카오/JWT), 문서 멀티 업로드 통신, 공공데이터 API, 세션 이력은 **김예담 담당**으로 별도 명세.

## 상태 범례
| 표기 | 의미 |
|---|---|
| ✅ | REST 엔드포인트 구현·검증 완료 |
| 🧩 | 서비스 계층 구현 완료(REST 미노출, CLI 하니스로 검증) |
| 📝 | 예정 — 아래 스키마는 FE 연동 계약(서비스 반환 구조와 동일) |

## 공통 규약
- **도메인 enum**: `road` | `safety` | `traffic` | `etc`
- **에러 형식** (FastAPI 표준): `{ "detail": "<메시지>" }`
- **주요 상태코드**: `200` 성공 · `415` 미지원 형식 · `404` 없음 · `422` 요청 검증 실패 · `500` 처리 오류

---

## 1. 시스템

### ✅ GET `/health`
서비스 상태 및 런타임 설정 조회.

**응답 200**
```json
{
  "status": "ok",
  "app": "trie-backend",
  "version": "0.1.0",
  "embedding_backend": "bge-m3",
  "chunk_strategy": "semantic"
}
```

---

## 2. 문서 수집 (documents) — vikira ①②③⑤

### ✅ POST `/api/v1/documents/ingest`
비정형 문서를 업로드하면 **파싱 → 시맨틱 청킹 → BGE-m3 임베딩 → ChromaDB 적재**까지 수행하고 메타데이터를 RDBMS에 저장한다.

> 프로덕션 멀티 업로드 통신은 김예담 담당. 본 엔드포인트는 파이프라인 단독 구동용.

**요청** `multipart/form-data`
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `file` | file | ✔ | `.pdf` `.docx` `.txt` `.md` |
| `domain` | string | ✖ | 기본 `etc` |

**응답 200** — `IngestResponse`
```json
{
  "document_id": 1,
  "title": "도로 유지보수 지침서",
  "doc_type": "pdf",
  "domain": "road",
  "status": "indexed",
  "char_count": 12034,
  "chunk_count": 18,
  "elapsed_sec": 7.42,
  "chunk_preview": [
    { "index": 0, "char_count": 812, "token_estimate": 325, "text": "포트홀 보수는 ..." }
  ]
}
```
**에러**: `415` 미지원 형식 · `500` 수집 실패

**예시**
```bash
curl -F "file=@지침서.pdf" -F "domain=road" http://localhost:8000/api/v1/documents/ingest
```

### ✅ GET `/api/v1/documents`
수집된 문서 목록(최신순).

**응답 200** — `DocumentOut[]`
```json
[
  { "id": 1, "title": "도로 유지보수 지침서", "doc_type": "pdf", "domain": "road",
    "status": "indexed", "char_count": 12034, "chunk_count": 18,
    "created_at": "2026-07-01T09:12:33" }
]
```

### ✅ GET `/api/v1/documents/{document_id}`
단일 문서 조회. **에러**: `404` 없음.

---

## 3. 멀티모달 질의 분석 — vikira ②

### 🧩 서비스 `analyze_multimodal(text, image_path?, domain) -> UnifiedQuery`
이미지가 있으면 VLM(Gemini)으로 시각적 맥락을 추출하고, 텍스트 질의와 논리적으로 병합해 통합 쿼리를 만든다.
CLI: `python -m scripts.analyze_sample --text "..." --image road.png --domain road`

### ✅ POST `/api/v1/search/analyze`
**요청** `multipart/form-data`: `text`(필수), `image`(선택, 이미지 파일), `domain`(선택)

**응답** — `UnifiedQuery`
```json
{
  "unified_query": "노란 차선 위 포트홀의 보수 절차와 관련 규정",
  "keywords": ["포트홀", "보수 절차", "도로법"],
  "domain_hint": "road",
  "visual_context": {
    "context_text": "회색 아스팔트 노면에 깊게 파인 포트홀과 방사형 균열이 보인다.",
    "labels": ["도로 노면", "포트홀", "균열"],
    "situation": "차선 위 노면 손상",
    "estimated_cause": "재료 피로 및 침수 추정"
  }
}
```
> `visual_context`는 이미지 미첨부 시 `null`.

---

## 4. 에이전트 라우팅 — vikira ③

### 🧩 서비스 `run_agent(query, domain_hint) -> AgentResult` (LangGraph)
질의를 분석해 **도메인 자율 태깅 · Intent · 모호성(Low-context) · 라우팅**을 한 번에 판단한다. 모호하면 검색을 보류하고 재질의 템플릿을 제시한다.
CLI: `python -m scripts.agent_sample --text "..."`

**`AgentResult`**
```json
{
  "query": "...", "domain": "road", "intent": "포트홀 보수 절차 확인",
  "intent_type": "절차문의",
  "route": "hybrid",                 // vector | keyword | hybrid | public_api | clarify
  "is_ambiguous": false, "ambiguity_score": 0.1,
  "missing_slots": [], "keywords": ["포트홀", "보수 절차"],
  "rationale": "키워드 정확성과 의미 탐색이 모두 필요",
  "template": null                    // route=clarify 일 때 { title, message, required[] }
}
```

---

## 5. 통합 검색 — vikira ③④  ·  FE "통합 검색 화면"

### ✅ POST `/api/v1/search`
멀티모달 분석 → 에이전트 라우팅 → 하이브리드 검색(**벡터 코사인 + RDBMS 키워드/정규식**) → **Cross-Encoder 재정렬** → **컨텍스트 절삭**까지 한 번에 수행.

**요청** `multipart/form-data`: `text`(필수), `image`(선택), `domain`(선택)

**응답** — `{ agent: AgentResult, search: SearchResult | null }`
```json
{
  "agent": { "route": "hybrid", "domain": "road", "keywords": ["포트홀","보수"], "...": "..." },
  "search": {
    "route": "hybrid",
    "query": "포트홀 보수 절차",
    "hits": [
      { "source": "vector", "document_id": 1, "chunk_index": 4,
        "score": 0.872, "domain": "road", "text": "포트홀은 아스팔트 절단 후 ..." }
    ],
    "used_tokens": 2019,
    "truncated": false,
    "note": null
  }
}
```
> **모호 질의**: `agent.route == "clarify"` → `search: null`, `agent.template`으로 재질의 유도.
> **공공데이터**: `route == "public_api"` → `search.note`에 위임 안내(실제 호출은 김예담 모듈).

### 🧩 서비스 `execute_search(query, route, keywords?, domain?) -> SearchResult`
CLI: `python -m scripts.search_sample --query "..." --auto`

---

## 6. 보고서 생성 — vikira ⑤

### ✅ POST `/api/v1/reports`
검색 결과(다중 출처 컨텍스트) + 도메인·보고서 타입별 서식을 결합해 LLM 메타 프롬프팅으로 **Markdown 실무 보고서 초안**을 생성한다.

**요청** `application/json`
```json
{
  "session_id": "선택(미지정 시 서버 생성)",
  "domain": "road",
  "report_type": "inspection_log",   // inspection_log | complaint_brief | improvement_reco | ...
  "query": "○○로 포트홀 현황 보고",
  "hits": [ /* /search 의 search.hits (선택; 미지정 시 query로 재검색) */ ]
}
```
**응답** — `GeneratedReport`
```json
{
  "id": 10, "session_id": "8f3c...", "domain": "road", "report_type": "inspection_log",
  "content": "# 도로 점검 일지\n\n## 개요\n...",
  "sources": [ { "document_id": 1, "chunk_index": 4 } ],
  "created_at": "2026-07-01T10:20:00"
}
```

---

## 데이터 모델 (Entity)

| 모델 | 핵심 필드 | 비고 |
|---|---|---|
| **KnowledgeDocument** | id, title, doc_type, domain, status, char_count, chunk_count, raw_text, meta, created_at | 사내 문서 원본 |
| **DocumentChunk** | id, document_id, chunk_index, text, char_count, token_estimate, vector_id, meta | ChromaDB `vector_id` 연결 |
| **VisualResource** | id, source_path, domain, vlm_context, labels[], meta, created_at | 현장 이미지 + VLM 맥락 |
| **GeneratedReport** | id, session_id, domain, report_type, content, sources[], meta, created_at | AI 보고서 초안 |

`status`: `pending` → `parsed` → `chunked` → `indexed` (실패 시 `failed`)

---

## 부록 — 김예담 담당 API (별도 명세)
| 영역 | 엔드포인트(안) |
|---|---|
| 인증 | `POST /auth/kakao`, `POST /auth/refresh` (JWT Access/Refresh) |
| 업로드 통신 | 문서 멀티 업로드 트랜스포트 → 본 문서 §2 파이프라인 호출 |
| 공공데이터 | API 카탈로그 등록 · 동적 파라미터 조립 · On-demand 호출 · Fallback |
| 이력 | 세션별 질의/이미지/검색결과/보고서 로깅·복원 |
