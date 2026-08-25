from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DocumentMetadata:
    document_id: str
    document_type: str
    number: str
    year: int
    title: str
    detail_url: str
    source_url: str
    pdf_path: str = ""
    status: str = "tidak_diketahui"
    amends: str = ""
    repeals: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArticleChunk:
    chunk_id: str
    document_id: str
    article: str
    text: str
    title: str
    document_type: str
    number: str
    year: int
    source_url: str
    status: str = "tidak_diketahui"
    amends: str = ""
    repeals: str = ""

    def metadata(self) -> dict[str, str | int]:
        return {
            "document_id": self.document_id,
            "article": self.article,
            "title": self.title,
            "document_type": self.document_type,
            "number": self.number,
            "year": self.year,
            "source_url": self.source_url,
            "status": self.status,
            "amends": self.amends,
            "repeals": self.repeals,
        }
