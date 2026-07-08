"""FNC-HIS-01 — /search 이미지 메타 응답 + 세션 이력에 이미지 포함 테스트."""

from __future__ import annotations

import io

from sqlalchemy import select

from app.models import SearchHistory

_PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x00\x03\x00\x01\x9a\x92\xdd\xcc\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_search_response_and_history_include_image(client, db):
    r = client.post(
        "/api/v1/search",
        data={"text": "포트홀 보수 절차", "domain": "road"},
        files={"image": ("pothole.png", io.BytesIO(_PNG_1PX), "image/png")},
        headers={"X-Session-Id": "img-session-1"},
    )
    assert r.status_code == 200, r.text
    body = r.json()

    # 응답에 이미지 메타 포함 (path=서버 저장 경로, filename=원본명)
    assert body["image"] is not None
    assert body["image"]["filename"] == "pothole.png"
    assert body["image"]["path"]

    # 이력 미들웨어가 응답 전체를 스냅샷으로 저장 → '연동 이미지'가 이력에 남는다
    row = db.scalar(select(SearchHistory).where(SearchHistory.session_uuid == "img-session-1"))
    assert row is not None
    assert row.result_snapshot.get("image", {}).get("filename") == "pothole.png"


def test_search_without_image_has_null_image(client):
    r = client.post("/api/v1/search", data={"text": "포트홀 보수 절차"})
    assert r.status_code == 200
    assert r.json()["image"] is None
