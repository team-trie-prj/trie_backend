"""phase ⑤ 보고서 생성 단위 테스트 (LLM 불필요 — Mock/Fake)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import GeneratedReport
from app.search.schemas import SearchHit
from app.services.report_service import generate_report


class FakeLLM:
    def generate_text(self, prompt, system=None, json=False) -> str:
        return "# 점검 일지\n\n## 개요\n포트홀 보수 관련 초안입니다 [1]."

    def generate_vision(self, prompt, image_paths, system=None, json=False) -> str:
        return "{}"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _hits():
    return [
        SearchHit("vector", 1, 4, "포트홀은 절단 후 채움재로 보수한다.", 0.9, "road"),
        SearchHit("keyword", 1, 2, "도로 균열 보수 절차 규정.", 0.7, "road"),
    ]


def test_generate_report_persists_and_cites(db):
    out = generate_report(
        "포트홀 현황 보고", _hits(), domain="road",
        report_type="inspection_log", db=db, client=FakeLLM(),
    )
    assert out["id"] is not None
    assert out["session_id"]
    assert out["content"].startswith("#")
    assert len(out["sources"]) == 2
    # DB 저장 확인
    row = db.get(GeneratedReport, out["id"])
    assert row is not None
    assert row.report_type == "inspection_log"
    assert row.meta["n_context"] == 2


def test_generate_report_generates_session_id_when_absent(db):
    out = generate_report("x", _hits(), db=db, client=FakeLLM())
    assert len(out["session_id"]) >= 16  # uuid4 hex


def test_generate_report_empty_hits_returns_shortage_note(db):
    out = generate_report("근거 없음", [], domain="road", db=db, client=FakeLLM())
    assert "자료 부족" in out["content"]
    assert out["sources"] == []


def test_generate_report_without_db_skips_persist():
    out = generate_report("x", _hits(), client=FakeLLM())  # db 없음
    assert out["id"] is None
    assert out["content"]


def test_report_types_include_fe_values():
    from app.services.report_service import _report_meta

    assert _report_meta("inspection_log")["name"] == "점검 일지"
    assert _report_meta("civil_brief")["name"] == "민원 대응 브리핑"
    assert _report_meta("analysis")["name"] == "분석 보고서"


class _BoomLLM:
    def generate_text(self, *args, **kwargs):
        raise RuntimeError("LLM down")

    def generate_vision(self, *args, **kwargs):
        raise RuntimeError("LLM down")


def test_generate_report_survives_llm_error(db):
    # LLM 실패 시 500 대신 안내 초안 반환 (동반 장애 방지)
    out = generate_report("포트홀 보고", _hits(), db=db, client=_BoomLLM())
    assert out["id"] is not None
    assert "실패" in out["content"]
