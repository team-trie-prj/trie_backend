"""모호 질의 보완용 도메인별 재질의 템플릿 (Low-context Detection 후 제시)."""

from __future__ import annotations

DOMAIN_TEMPLATES: dict[str, dict] = {
    "road": {
        "title": "도로 시설물 질의 보완",
        "slots": [
            "위치(도로명/구간/좌표)",
            "파손 유형(포트홀/균열/침하 등)",
            "발생·점검 시기",
            "심각도/통행 영향",
        ],
    },
    "safety": {
        "title": "산업안전 질의 보완",
        "slots": [
            "현장/공정",
            "위험 요소(추락/끼임/전도 등)",
            "관련 설비·작업",
            "발생 시점",
        ],
    },
    "traffic": {
        "title": "교통 질의 보완",
        "slots": [
            "구간/지점",
            "시간대",
            "현황 유형(교통량/사고/신호)",
            "대상 기간",
        ],
    },
    "etc": {
        "title": "질의 보완",
        "slots": ["대상/주제", "기간", "원하는 결과(검색/통계/보고서)"],
    },
}


def build_template(domain: str, missing_slots: list[str] | None = None) -> dict:
    base = DOMAIN_TEMPLATES.get(domain, DOMAIN_TEMPLATES["etc"])
    slots = missing_slots if missing_slots else base["slots"]
    return {
        "title": base["title"],
        "message": "질의가 모호하거나 필수 정보가 부족합니다. 아래 항목을 채워 다시 질문해 주세요.",
        "required": slots,
    }
