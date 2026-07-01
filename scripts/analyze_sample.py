"""멀티모달 질의 분석 CLI 하니스 (phase ②).

사용 예:
  python -m scripts.analyze_sample --text "포트홀 보수 절차" --image road.jpg --domain road
  python -m scripts.analyze_sample --text "교통 정체 원인" --provider mock   # API 없이 검증
"""

from __future__ import annotations

import argparse
import json
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="multimodal query analysis harness")
    parser.add_argument("--text", required=True, help="사용자 자연어 질의")
    parser.add_argument("--image", default=None, help="첨부 이미지 경로(선택)")
    parser.add_argument("--domain", default="etc", choices=["road", "safety", "traffic", "etc"])
    parser.add_argument("--provider", default=None, choices=["gemini", "mock"],
                        help="LLM 제공자 강제(미지정 시 .env)")
    parser.add_argument("--out", default=None, help="결과 JSON 을 UTF-8 파일로 저장")
    args = parser.parse_args()

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    from app.services.multimodal import analyze_multimodal

    result = analyze_multimodal(args.text, image_path=args.image, domain=args.domain)
    payload = json.dumps(result.as_dict(), ensure_ascii=False, indent=2)

    print(payload)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)


if __name__ == "__main__":
    main()
