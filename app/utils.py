"""공용 유틸 (김예담).

`datetime.utcnow()` 는 Python 3.12+ 에서 deprecated — aware API 로 얻되,
DB(DateTime naive 컬럼)·JWT 기존 포맷과의 호환을 위해 naive UTC 로 반환한다.
"""

from __future__ import annotations

import datetime


def utcnow() -> datetime.datetime:
    """현재 UTC 시각 (naive) — deprecated utcnow() 대체."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
