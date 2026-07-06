"""SQLAlchemy ORM 모델.

명세서 Entity 매핑:
  - KnowledgeDocument / DocumentChunk : 사내 문서 원본 + 청크(vikira ①②③⑤ 소유)
  - VisualResource                    : 현장 이미지 + VLM 맥락 (phase ② 에서 채움)
  - GeneratedReport                   : AI 보고서 초안 (phase ⑤ 에서 채움)

공용 스키마 — 세부 동기화/정제는 김예담(RDBMS 메타데이터 동기화)과 맞물림.
"""

from .api_key import ApiKey
from .knowledge import DocStatus, DocumentChunk, Domain, KnowledgeDocument
from .public_catalog import PublicApiCatalog
from .report import GeneratedReport
from .search_history import SearchHistory
from .user import RefreshToken, User
from .visual import VisualResource

__all__ = [
    "Domain",
    "DocStatus",
    "KnowledgeDocument",
    "DocumentChunk",
    "VisualResource",
    "GeneratedReport",
    "User",
    "RefreshToken",
    "ApiKey",
    "PublicApiCatalog",
    "SearchHistory",
]
