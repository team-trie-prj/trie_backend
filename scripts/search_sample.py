"""검색 실행 CLI 하니스 (phase ④).

사용 예:
  # 라우팅 직접 지정
  python -m scripts.search_sample --query "포트홀 보수 절차" --route hybrid --domain road
  # 에이전트가 라우팅 결정 → 검색까지 자동 (end-to-end)
  python -m scripts.search_sample --query "포트홀 보수 절차와 규정" --auto
  # 모델 없이 검증: 임베딩 hashing + 재정렬 none
  python -m scripts.search_sample --query "포트홀" --route keyword --rerank none
"""

from __future__ import annotations

import argparse
import json
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="search execution harness")
    parser.add_argument("--query", required=True)
    parser.add_argument("--route", default="hybrid",
                        choices=["vector", "keyword", "hybrid", "public_api", "clarify"])
    parser.add_argument("--domain", default=None, choices=["road", "safety", "traffic", "etc"])
    parser.add_argument("--keywords", default=None, help="쉼표 구분 키워드(미지정 시 query 사용)")
    parser.add_argument("--regex", default=None, help="정규식 정밀 필터(선택)")
    parser.add_argument("--auto", action="store_true", help="에이전트가 라우팅 결정 후 검색")
    parser.add_argument("--backend", default=None, choices=["bge-m3", "hashing"])
    parser.add_argument("--rerank", default=None, choices=["cross-encoder", "none"])
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.backend:
        os.environ["EMBEDDING_BACKEND"] = args.backend

    from app.services.search_service import execute_search

    route, domain = args.route, args.domain
    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None

    if args.auto:
        from app.agent import run_agent

        decision = run_agent(args.query, domain_hint=domain or "etc")
        route, domain, keywords = decision.route, decision.domain, decision.keywords
        print(f"[agent] route={route} domain={domain} keywords={keywords}")
        if decision.template:
            print("[agent] 모호 질의 — 재질의 템플릿:")
            print(json.dumps(decision.template, ensure_ascii=False, indent=2))

    result = execute_search(
        args.query, route=route, keywords=keywords, domain=domain,
        regex=args.regex, rerank_backend=args.rerank,
    )
    payload = json.dumps(result.as_dict(), ensure_ascii=False, indent=2)
    print(payload)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)


if __name__ == "__main__":
    main()
