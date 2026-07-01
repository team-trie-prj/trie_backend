# trie_backend

멀티모달 + 에이전트 기반 **하이브리드 RAG 통합 검색 시스템** 백엔드.
사내 비정형 문서와 공공데이터를 융합 탐색하고 실무 보고서를 자동 생성한다.
(오렌지파이 5 Plus 자체 서버 환경 최적화 · LLM/VLM 은 무료 API/로컬로 위임)

## 스택
FastAPI · Python 3.10 · SQLAlchemy · PostgreSQL(운영) / SQLite(개발) · ChromaDB ·
BGE-m3(로컬 임베딩, 무료) · Cross-Encoder(bge-reranker-v2-m3 재정렬) · LangGraph(에이전트) · LLM/VLM = Gemini 무료 티어(gemini-2.5-flash) / Ollama

---

## vikira 담당 — RAG / AI 파이프라인

### ✅ 수집 파이프라인 (ingestion)
| 작업 | 모듈 |
|---|---|
| 문서 파싱 + 노이즈 필터링 (PDF/DOCX) | `app/pipeline/parsing.py` |
| 시맨틱 청킹 + 오버랩 | `app/pipeline/chunking.py` |
| BGE-m3 임베딩 (지연로딩 + 무비용 해싱 폴백) | `app/pipeline/embedding.py` |
| ChromaDB 코사인 인덱싱/적재 | `app/vectorstore/chroma.py` |
| 수집 오케스트레이션 | `app/services/ingestion.py` |

### ✅ 멀티모달 질의 분석 (multimodal)
| 작업 | 모듈 |
|---|---|
| VLM 이미지 시각적 맥락 추출 | `app/services/multimodal.py` |
| 텍스트 질의 + 이미지 맥락 논리적 병합 | `app/services/multimodal.py` |
| LLM/VLM 클라이언트 (Gemini + Mock 폴백) | `app/llm/` |

### ✅ 에이전트 라우팅 (agent, LangGraph)
| 작업 | 모듈 |
|---|---|
| 대상 도메인 자율 태깅 (road/safety/traffic/etc) | `app/agent/analyzer.py` |
| 사용자 질의 궁극적 의도(Intent) 분석 | `app/agent/analyzer.py` |
| 질의 모호성 평가(Low-context) + 재질의 템플릿 | `app/agent/analyzer.py`, `templates.py` |
| 하이브리드 RAG 탐색 경로 자율 선택 | `app/agent/graph.py` (analyze→clarify/route) |

### ✅ 검색 실행 (search)
| 작업 | 모듈 |
|---|---|
| Vector 코사인 의미 탐색 | `app/search/vector.py` |
| RDBMS 키워드/정규식 정밀 탐색 | `app/search/keyword.py` |
| Cross-Encoder 재정렬 (bge-reranker-v2-m3) | `app/search/rerank.py` |
| LLM 컨텍스트 절삭 | `app/search/truncate.py` |
| 검색 오케스트레이션 (route→실행→병합→재정렬→절삭) | `app/services/search_service.py` |

### ⏳ 이후
보고서 생성 — 검색 결과 + 서식 결합 LLM 메타 프롬프팅

> 인증/보안/공공API 연동/DB 동기화/세션·이력 등은 김예담 담당과 맞물린다.
> 업로드 통신 로직은 김예담 소유이며, 본 파이프라인의 `ingestion` 서비스를 호출하는 구조.

---

## 빠른 시작

```bash
# 1) 가상환경 + 의존성
python -m venv .venv && .venv\Scripts\activate      # (Windows)
pip install -r requirements.txt

# 2) 환경설정
copy .env.example .env                               # 필요 시 값 수정

# 3) API 서버
uvicorn app.main:app --reload
#   -> http://127.0.0.1:8000/docs  (Swagger)
#   -> http://127.0.0.1:8000/health
```

## 수집 파이프라인 단독 실행 (CLI 하니스)

```bash
# 실제 BGE-m3 임베딩 (최초 1회 모델 ~2.3GB 다운로드)
python -m scripts.ingest_sample "docs/안전지침서.pdf" --domain safety

# torch/모델 없이 즉시 검증 (비용·다운로드 0) — 개발용 해싱 임베더
python -m scripts.ingest_sample "docs/sample.pdf" --backend hashing --query "포트홀 보수 절차"
```

### 임베딩 백엔드 전환
`.env` 의 `EMBEDDING_BACKEND` 로 제어한다.
- `bge-m3` : 실제 BAAI/bge-m3 (로컬, 무료, 한국어 우수) — 최초 실행 시 모델 자동 다운로드
- `hashing`: zero-dependency 대체 임베더 (개발/테스트/오프라인)

## 멀티모달 질의 분석 (CLI 하니스)

```bash
# 실제 Gemini VLM (.env 의 GEMINI_API_KEY 필요, 기본 모델 gemini-2.5-flash)
python -m scripts.analyze_sample --text "이 도로 보수 절차" --image road.png --domain road

# API 없이 구조 검증 (Mock 폴백)
python -m scripts.analyze_sample --text "교통 정체 원인" --provider mock
```
> `LLM_PROVIDER` 로 제어. 키가 없거나 `mock` 이면 자동으로 Mock 클라이언트로 폴백한다.

## 에이전트 라우팅 (CLI 하니스)

```bash
python -m scripts.agent_sample --text "○○로 3.2km 포트홀 보수 절차와 법령" --domain road
python -m scripts.agent_sample --text "그거 알려줘" --provider mock
```
> 결과: domain · intent · route(`vector|keyword|hybrid|public_api|clarify`) · keywords, 모호 시 재질의 template.

## 검색 실행 (CLI 하니스)

```bash
# 에이전트 라우팅 → 검색까지 자동 (end-to-end)
python -m scripts.search_sample --query "포트홀 보수 절차와 규정" --auto
# 모델 없이 검증: 재정렬 생략
python -m scripts.search_sample --query "포트홀" --route keyword --rerank none
```

## 테스트
```bash
pytest            # torch/모델 불필요 (HashingEmbedder 사용)
```

## 디렉터리
```
app/
  config.py            설정(.env)
  database.py          SQLAlchemy 엔진/세션
  models/              KnowledgeDocument·DocumentChunk·VisualResource·GeneratedReport
  pipeline/            parsing · chunking · embedding    (수집)
  vectorstore/         chroma (ChromaDB 코사인)           (수집)
  llm/                 base · gemini · mock              (멀티모달 LLM/VLM)
  agent/               analyzer · graph(LangGraph) · templates  (에이전트 라우팅)
  search/              vector · keyword · rerank · truncate      (검색 실행)
  services/            ingestion · multimodal · search_service
  api/documents        수집/조회 API (검증용 하니스)
scripts/               ingest_sample · analyze_sample · agent_sample · search_sample
tests/                 파이프라인 · 멀티모달 · 에이전트 · 검색 단위 테스트
data/                  로컬 산출물(sqlite·chroma·uploads) — git 제외
```
