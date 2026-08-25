from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader

from lexnusa.models import ArticleChunk, DocumentMetadata

ARTICLE_PATTERN = re.compile(r"(?im)^\s*(Pasal\s+\d+[A-Z]?)\s*$")
WHITESPACE_PATTERN = re.compile(r"[ \t]+")


def extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [WHITESPACE_PATTERN.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def chunk_articles(text: str, metadata: DocumentMetadata) -> list[ArticleChunk]:
    normalized = normalize_text(text)
    matches = list(ARTICLE_PATTERN.finditer(normalized))
    if not matches:
        return []
    chunks: list[ArticleChunk] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        body = normalized[match.end() : end].strip()
        if not body:
            continue
        article = match.group(1).title()
        chunks.append(
            ArticleChunk(
                chunk_id=f"{metadata.document_id}:{article.lower().replace(' ', '-')}",
                document_id=metadata.document_id,
                article=article,
                text=f"{article}\n{body}",
                title=metadata.title,
                document_type=metadata.document_type,
                number=metadata.number,
                year=metadata.year,
                source_url=metadata.source_url,
                status=metadata.status,
                amends=metadata.amends,
                repeals=metadata.repeals,
            )
        )
    return chunks


def parse_raw_directory(raw_dir: Path, output_path: Path) -> list[ArticleChunk]:
    chunks: list[ArticleChunk] = []
    for metadata_path in sorted(raw_dir.glob("*.json")):
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        allowed = DocumentMetadata.__dataclass_fields__.keys()
        metadata = DocumentMetadata(**{key: payload[key] for key in allowed if key in payload})
        pdf_path = Path(metadata.pdf_path)
        if not pdf_path.is_absolute():
            pdf_path = Path.cwd() / pdf_path
        chunks.extend(chunk_articles(extract_pdf_text(pdf_path), metadata))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as stream:
        for chunk in chunks:
            stream.write(json.dumps({**chunk.metadata(), "chunk_id": chunk.chunk_id, "text": chunk.text}, ensure_ascii=False) + "\n")
    return chunks
