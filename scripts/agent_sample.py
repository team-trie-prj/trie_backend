"""에이전트 라우팅 CLI 하니스 (phase ③).

사용 예:
  python -m scripts.agent_sample --text "○○로 3.2km 포트홀 보수 절차와 규정"
  python -m scripts.agent_sample --text "그거 어떻게 해?" --provider mock
"""

from __future__ import annotations

import argparse
import json
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="hybrid RAG routing agent harness")
    parser.add_argument("--text", required=True, help="사용자 질의")
    parser.add_argument("--domain", default="etc", choices=["road", "safety", "traffic", "etc"],
                        help="도메인 힌트(선택)")
    parser.add_argument("--image-context", default=None, help="이미지 분석 맥락(선택)")
    parser.add_argument("--provider", default=None, choices=["gemini", "mock"])
    parser.add_argument("--out", default=None, help="결과 JSON 을 UTF-8 파일로 저장")
    args = parser.parse_args()

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    from app.agent import run_agent

    result = run_agent(args.text, domain_hint=args.domain, image_context=args.image_context)
    payload = json.dumps(result.as_dict(), ensure_ascii=False, indent=2)

    print(payload)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)


if __name__ == "__main__":
    main()
