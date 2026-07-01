"""수집 파이프라인 CLI 하니스.

사용 예:
  python -m scripts.ingest_sample "C:/path/to/doc.pdf" --domain road
  python -m scripts.ingest_sample doc.pdf --backend hashing --query "포트홀 보수 절차"

--backend hashing 을 주면 torch/BGE-m3 모델 없이(비용·다운로드 0) 전 구간을 즉시 검증한다.
"""

from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="trie ingestion pipeline harness")
    parser.add_argument("path", help="문서 경로 (PDF/DOCX/TXT)")
    parser.add_argument("--domain", default="etc", choices=["road", "safety", "traffic", "etc"])
    parser.add_argument("--backend", default=None, choices=["bge-m3", "hashing"],
                        help="임베딩 백엔드 강제 (미지정 시 .env)")
    parser.add_argument("--strategy", default=None, choices=["semantic", "recursive"])
    parser.add_argument("--query", default=None, help="적재 후 코사인 검색 테스트 질의")
    args = parser.parse_args()

    # 설정 캐시 전에 환경변수 오버라이드
    if args.backend:
        os.environ["EMBEDDING_BACKEND"] = args.backend
    if args.strategy:
        os.environ["CHUNK_STRATEGY"] = args.strategy

    from app.config import get_settings
    from app.database import SessionLocal, init_db
    from app.services.ingestion import ingest_file

    settings = get_settings()
    init_db()

    print(f"[config] backend={settings.embedding_backend} strategy={settings.chunk_strategy}")
    print(f"[ingest] {args.path} (domain={args.domain}) ...")

    db = SessionLocal()
    try:
        result = ingest_file(path=args.path, db=db, domain=args.domain)
    finally:
        db.close()

    print("\n=== 결과 ===")
    print(f"  document_id : {result.document_id}")
    print(f"  title       : {result.title}")
    print(f"  type/domain : {result.doc_type} / {result.domain}")
    print(f"  status      : {result.status}")
    print(f"  chars       : {result.char_count:,}")
    print(f"  chunks      : {result.chunk_count}")
    print(f"  elapsed     : {result.elapsed_sec}s")
    for c in result.chunk_preview:
        print(f"    - #{c['index']} ({c['char_count']}자, ~{c['token_estimate']}tok) {c['text']}")

    if args.query:
        from app.pipeline.embedding import get_embedder
        from app.vectorstore import get_vector_store

        qvec = get_embedder().embed_query(args.query)
        res = get_vector_store().query(qvec, n_results=3)
        print(f"\n=== 코사인 검색: '{args.query}' ===")
        docs = res.get("documents", [[]])[0]
        dists = res.get("distances", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        for i, (d, dist, m) in enumerate(zip(docs, dists, metas, strict=False)):
            snippet = d[:120].replace("\n", " ")
            loc = f"doc {m.get('document_id')}#{m.get('chunk_index')}"
            print(f"  {i + 1}. dist={dist:.4f} [{loc}] {snippet}…")


if __name__ == "__main__":
    main()
