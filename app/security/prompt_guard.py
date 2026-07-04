"""시스템 프롬프트 인젝션 1차 필터 — 규칙(정규식) 기반 (김예담).

목적: 사용자 제공 자연어(업로드 문서 본문·질의 등)에 섞인 프롬프트 인젝션 시도를
      LLM 에 닿기 전에 1차로 탐지/차단한다.
      (심층 LLM 기반 2차 탐지는 vikira/범위 밖 — 여기선 고신호 규칙만.)

한국어 + 영어 공격 패턴을 커버하며, 오탐을 줄이기 위해 구체적 문구만 매칭한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# (패턴명, 정규식) — 각 패턴은 고신호(specific)로 설계해 일반 문서 오탐 최소화
INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    # 지시 무효화
    ("instruction_override_en", re.compile(
        r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|preceding)\s+"
        r"(instruction|prompt|message|context|rule)", re.I)),
    ("instruction_override_ko", re.compile(
        r"(이전|위의|앞의|기존|지금까지)[^\n]{0,14}(지시|명령|지침|프롬프트|규칙|설정)"
        r"[^\n]{0,14}(무시|잊(어|고)|삭제|무효|따르지\s*마)")),
    ("disregard_en", re.compile(r"disregard\s+(all\s+|the\s+)?(previous|prior|above|your)", re.I)),
    # 역할 탈취 / 재정의
    ("role_hijack_en", re.compile(
        r"\b(you\s+are\s+now|from\s+now\s+on\s+you|act\s+as\s+(an?|the)|"
        r"pretend\s+to\s+be|ignore\s+your\s+(role|persona|guidelines?))\b", re.I)),
    ("role_hijack_ko", re.compile(
        r"(지금부터|이제부터|앞으로)[^\n]{0,10}(너는|당신은|넌|네가|역할)")),
    # 시스템 프롬프트 유출 유도
    ("prompt_leak_en", re.compile(
        r"(reveal|show|print|repeat|expose|leak|tell\s+me|what\s+(is|are))[^\n]{0,24}"
        r"(system\s*)?(prompt|instruction|guideline)", re.I)),
    ("prompt_leak_ko", re.compile(
        r"(시스템\s*)?(프롬프트|지시문|지침|규칙)[을를]?\s*[^\n]{0,6}(알려|보여|출력|공개|말해|노출)")),
    # 탈옥 / 안전장치 우회
    ("jailbreak_en", re.compile(
        r"\b(developer\s+mode|jailbreak|DAN\s+mode|do\s+anything\s+now|"
        r"without\s+(any\s+)?(restriction|filter|censorship)|"
        r"ignore\s+(all\s+)?(safety|content)\s+(polic|filter|guideline))", re.I)),
    ("jailbreak_ko", re.compile(r"(탈옥|제한\s*(없이|해제)|검열\s*없|안전장치\s*(무시|해제))")),
    # 프롬프트 구조/역할 토큰 주입
    ("role_token", re.compile(
        r"<\|?\s*(system|assistant|user)\s*\|?>|\[/?INST\]|###\s*(system|instruction)", re.I)),
    ("role_prefix", re.compile(r"(?mi)^\s*(system|assistant)\s*:\s")),
]


@dataclass
class ScanResult:
    flagged: bool
    matches: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"flagged": self.flagged, "matches": self.matches}


def scan_text(text: str | None) -> ScanResult:
    """텍스트에서 프롬프트 인젝션 패턴을 탐지. 하나라도 매칭되면 flagged."""
    if not text:
        return ScanResult(False, [])
    hits = [name for name, pattern in INJECTION_PATTERNS if pattern.search(text)]
    return ScanResult(bool(hits), hits)
