"""⑤ 검색 데이터 + 서식 결합 LLM 메타 프롬프팅  (FNC-REP-01)

하이브리드 검색 결과(다중 출처 컨텍스트)를 도메인·보고서 타입별 서식과 결합해
LLM(Gemini)으로 Markdown 실무 보고서 초안을 생성한다.
- 각 근거에 [n] 출처 표기 → 할루시네이션 억제
- 세션 식별자(session_id)와 출처 메타데이터를 GeneratedReport 에 저장
"""

from __future__ import annotations

import uuid

from ..llm import get_llm_client
from ..models import GeneratedReport
from ..search.schemas import SearchHit

# 보고서 타입별 서식(섹션 구성)
REPORT_TYPES: dict[str, dict] = {
    # FE 양식 3종 (safety-check / civil-brief / analysis) 매핑값
    "inspection_log": {
        "name": "점검 일지",
        "sections": ["개요", "점검 내용", "발견 사항", "조치 필요사항"],
    },
    "civil_brief": {
        "name": "민원 대응 브리핑",
        "sections": ["민원 요지", "현황", "대응 방안", "근거 규정"],
    },
    "analysis": {
        "name": "분석 보고서",
        "sections": ["현황 분석", "원인 추정", "시사점", "결론"],
    },
    # 추가 서식(선택)
    "improvement_reco": {
        "name": "개선 권고안",
        "sections": ["문제 정의", "분석", "개선 권고", "기대 효과"],
    },
    "situation_brief": {
        "name": "상황 브리핑",
        "sections": ["상황 요약", "세부 현황", "조치/판단", "참고 근거"],
    },
}
DEFAULT_TYPE = "inspection_log"


def _report_meta(report_type: str) -> dict:
    return REPORT_TYPES.get(report_type, REPORT_TYPES[DEFAULT_TYPE])


def _build_context(hits: list[SearchHit]) -> str:
    lines = []
    for i, h in enumerate(hits, start=1):
        src = f"문서{h.document_id} #{h.chunk_index}" if h.document_id is not None else h.source
        text = " ".join(h.text.split())
        lines.append(f"[{i}] (출처: {src}) {text}")
    return "\n".join(lines)


def _system_prompt(domain: str, report_type: str) -> str:
    meta = _report_meta(report_type)
    return (
        f"당신은 {domain} 도메인 실무 보고서 작성 전문가입니다. "
        f"'{meta['name']}'을(를) Markdown 으로 작성합니다. "
        "반드시 제공된 [n] 근거만 사용하고, 각 사실 문장 끝에 근거 번호를 [n] 형식으로 표기하세요. "
        "근거에 없는 내용은 추측하지 말고 '자료 없음'으로 표시합니다."
    )


def _report_prompt(query: str, context: str, report_type: str) -> str:
    meta = _report_meta(report_type)
    sections = "\n".join(f"## {s}" for s in meta["sections"])
    return (
        f"[요청]\n{query}\n\n"
        f"[검색 근거]\n{context}\n\n"
        f"위 근거를 종합해 다음 서식의 '{meta['name']}' 초안을 작성하세요.\n"
        f"제목(#)과 아래 섹션(##)을 사용합니다:\n{sections}\n"
    )


def generate_report(
    query: str,
    hits: list[SearchHit],
    domain: str = "etc",
    report_type: str = DEFAULT_TYPE,
    session_id: str | None = None,
    db=None,
    client=None,
) -> dict:
    session_id = session_id or uuid.uuid4().hex
    meta = _report_meta(report_type)

    if not hits:
        content = "# 자료 부족\n\n참조할 검색 결과가 부족하여 보고서를 생성할 수 없습니다."
    else:
        client = client or get_llm_client()
        context = _build_context(hits)
        content = client.generate_text(
            _report_prompt(query, context, report_type),
            system=_system_prompt(domain, report_type),
        )

    sources = [
        {"document_id": h.document_id, "chunk_index": h.chunk_index, "source": h.source}
        for h in hits
    ]

    report_id = None
    created_at = None
    if db is not None:
        row = GeneratedReport(
            session_id=session_id,
            domain=domain,
            report_type=report_type,
            content=content,
            sources=sources,
            meta={"query": query, "report_name": meta["name"], "n_context": len(hits)},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        report_id = row.id
        created_at = row.created_at

    return {
        "id": report_id,
        "session_id": session_id,
        "domain": domain,
        "report_type": report_type,
        "content": content,
        "sources": sources,
        "created_at": created_at,
    }
