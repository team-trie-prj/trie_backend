"""검색 결과 스키마."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class SearchHit:
    source: str  # "vector" | "keyword"
    document_id: int | None
    chunk_index: int | None
    text: str
    score: float
    domain: str = "etc"
    vector_id: str | None = None
    meta: dict = field(default_factory=dict)

    def key(self) -> tuple:
        """중복 제거용 키 (문서/청크 단위)."""
        if self.vector_id:
            return ("vid", self.vector_id)
        return ("dc", self.document_id, self.chunk_index)

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "score": round(self.score, 4),
            "domain": self.domain,
            "text": self.text,
        }


@dataclass
class SearchResult:
    route: str
    query: str
    hits: list[SearchHit] = field(default_factory=list)
    used_tokens: int = 0
    truncated: bool = False
    note: str | None = None

    def as_dict(self) -> dict:
        d = asdict(self)
        d["hits"] = [h.as_dict() for h in self.hits]
        return d
