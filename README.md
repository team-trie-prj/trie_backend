# trie_backend

멀티모달 + 에이전트 기반 **하이브리드 RAG 통합 검색 시스템** 백엔드.
사내 비정형 문서와 공공데이터를 융합 탐색하고 실무 보고서를 자동 생성한다.
(오렌지파이 5 Plus 자체 서버 환경 최적화 · LLM/VLM 은 무료 API/로컬로 위임)

## 스택
FastAPI · Python 3.10 · SQLAlchemy · PostgreSQL(운영) / SQLite(개발) · ChromaDB ·
BGE-m3(로컬 임베딩, 무료) · Cross-Encoder(재정렬) · LLM/VLM = Gemini 무료 티어 / Ollama

---

## vikira 담당 — RAG / AI 파이프라인

| 단계 | 작업 | 모듈 | 상태 |
|---|---|---|---|
| ① | 문서 파싱 + 노이즈 필터링 | `app/pipeline/parsing.py` | ✅ |
| ② | 시맨틱 청킹 + 오버랩 | `app/pipeline/chunking.py` | ✅ |
| ③ | BGE-m3 임베딩 | `app/pipeline/embedding.py` | ✅ |
| ⑤ | ChromaDB 인덱싱/적재 | `app/vectorstore/chroma.py` | ✅ |
| — | 오케스트레이션 | `app/services/ingestion.py` | ✅ |
| 이후 | VLM 멀티모달 · 에이전트 라우팅 · 하이브리드 검색 · 재정렬 · 보고서 생성 | (예정) | ⏳ |

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
  pipeline/            parsing · chunking · embedding   (vikira 단계 ①②③)
  vectorstore/         chroma                            (vikira 단계 ⑤)
  services/ingestion   수집 오케스트레이션
  api/documents        수집/조회 API (검증용 하니스)
scripts/ingest_sample  CLI 하니스
tests/                 파이프라인 단위 테스트
data/                  로컬 산출물(sqlite·chroma·uploads) — git 제외
```
