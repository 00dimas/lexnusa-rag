from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from lexnusa.parsing import parse_raw_directory
from lexnusa.status import apply_legal_status

TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


class LocalHashEmbedding(EmbeddingFunction[Documents]):
    """Small offline baseline; replace with multilingual-e5 in production."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def __call__(self, input: Documents) -> Embeddings:
        vectors: list[list[float]] = []
        for text in input:
            vector = [0.0] * self.dimensions
            for token in TOKEN_PATTERN.findall(text.casefold()):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                value = int.from_bytes(digest, "big")
                vector[value % self.dimensions] += -1.0 if value & 1 else 1.0
            norm = math.sqrt(sum(item * item for item in vector)) or 1.0
            vectors.append([item / norm for item in vector])
        return vectors

    @staticmethod
    def name() -> str:
        return "lexnusa-local-hash"

    def get_config(self) -> dict[str, Any]:
        return {"dimensions": self.dimensions}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "LocalHashEmbedding":
        return LocalHashEmbedding(dimensions=int(config.get("dimensions", 384)))


def get_collection(chroma_dir: Path):
    client = chromadb.PersistentClient(path=str(chroma_dir))
    return client.get_or_create_collection(
        "lexnusa_articles", embedding_function=LocalHashEmbedding(), metadata={"hnsw:space": "cosine"}
    )


def index_chunks(processed_path: Path, chroma_dir: Path) -> int:
    collection = get_collection(chroma_dir)
    rows = apply_legal_status(
        [json.loads(line) for line in processed_path.read_text(encoding="utf-8").splitlines() if line]
    )
    if not rows:
        return 0
    collection.upsert(
        ids=[row["chunk_id"] for row in rows],
        documents=[row["text"] for row in rows],
        metadatas=[{key: value for key, value in row.items() if key not in {"chunk_id", "text"}} for row in rows],
    )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse PDF per pasal dan indeks ke Chroma")
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--processed", type=Path, default=Path("data/processed/articles.jsonl"))
    parser.add_argument("--chroma", type=Path, default=Path("data/chroma"))
    args = parser.parse_args()
    chunks = parse_raw_directory(args.raw, args.processed)
    count = index_chunks(args.processed, args.chroma)
    print(f"Selesai: {len(chunks)} chunk diparsing, {count} chunk diindeks")


if __name__ == "__main__":
    main()
