from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path
from typing import Any, Iterable

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from lexnusa.indexing import LocalHashEmbedding
from lexnusa.status import apply_legal_status

COLLECTION_NAME = "lexnusa_articles"
VECTOR_SIZE = 384


def get_qdrant_client(path: Path | None = None) -> QdrantClient:
    url = os.getenv("QDRANT_URL")
    if url:
        return QdrantClient(url=url, api_key=os.getenv("QDRANT_API_KEY"))
    return QdrantClient(path=str(path or Path("data/qdrant")))


def ensure_collection(client: QdrantClient) -> None:
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://lexnusa.id/chunks/{chunk_id}"))


def load_rows(processed_path: Path) -> list[dict[str, Any]]:
    if not processed_path.exists():
        raise FileNotFoundError(
            f"Chunk belum tersedia di {processed_path}. Jalankan parser atau berikan --raw."
        )
    return apply_legal_status(
        [json.loads(line) for line in processed_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    )


def batched(items: list[dict[str, Any]], size: int = 64) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def index_qdrant(processed_path: Path, qdrant_path: Path | None = None) -> int:
    rows = load_rows(processed_path)
    if not rows:
        return 0
    client = get_qdrant_client(qdrant_path)
    ensure_collection(client)
    embedder = LocalHashEmbedding(VECTOR_SIZE)
    for batch in batched(rows):
        vectors = embedder([row["text"] for row in batch])
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(id=point_id(row["chunk_id"]), vector=vector, payload=row)
                for row, vector in zip(batch, vectors)
            ],
            wait=True,
        )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse PDF per pasal dan indeks ke Qdrant")
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--processed", type=Path, default=Path("data/processed/articles.jsonl"))
    parser.add_argument("--qdrant", type=Path, default=Path("data/qdrant"))
    parser.add_argument(
        "--no-parse",
        action="store_true",
        help="Indeks ulang articles.jsonl tanpa memproses PDF mentah",
    )
    args = parser.parse_args()
    if not args.no_parse:
        from lexnusa.parsing import parse_raw_directory

        parse_raw_directory(args.raw, args.processed)
    count = index_qdrant(args.processed, args.qdrant)
    print(f"Selesai: {count} chunk diindeks ke Qdrant ({os.getenv('QDRANT_URL') or args.qdrant})")


if __name__ == "__main__":
    main()
