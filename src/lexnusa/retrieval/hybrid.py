from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from qdrant_client import QdrantClient

from lexnusa.indexing import LocalHashEmbedding
from lexnusa.qdrant_store import COLLECTION_NAME, get_qdrant_client

TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    text: str
    metadata: dict[str, str | int]
    score: float
    vector_rank: int | None = None
    lexical_rank: int | None = None
    rerank_score: float | None = None


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.casefold())


class BM25Index:
    def __init__(self, documents: list[tuple[str, str, dict[str, Any]]], k1: float = 1.5, b: float = 0.75) -> None:
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.tokens = [tokenize(text) for _, text, _ in documents]
        self.average_length = sum(map(len, self.tokens)) / max(len(self.tokens), 1)
        self.document_frequency: Counter[str] = Counter()
        for tokens in self.tokens:
            self.document_frequency.update(set(tokens))

    def search(self, query: str, limit: int) -> list[tuple[str, float]]:
        query_tokens = tokenize(query)
        scores: list[tuple[str, float]] = []
        total = len(self.documents)
        for (chunk_id, _, _), tokens in zip(self.documents, self.tokens):
            frequencies = Counter(tokens)
            score = 0.0
            for token in query_tokens:
                frequency = frequencies[token]
                if not frequency:
                    continue
                document_frequency = self.document_frequency[token]
                inverse_frequency = math.log(1 + (total - document_frequency + 0.5) / (document_frequency + 0.5))
                denominator = frequency + self.k1 * (1 - self.b + self.b * len(tokens) / max(self.average_length, 1))
                score += inverse_frequency * frequency * (self.k1 + 1) / denominator
            if score > 0:
                scores.append((chunk_id, score))
        return sorted(scores, key=lambda item: (-item[1], item[0]))[:limit]


def reciprocal_rank_fusion(rankings: Iterable[list[str]], k: int = 60) -> dict[str, float]:
    scores: defaultdict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, 1):
            scores[chunk_id] += 1.0 / (k + rank)
    return dict(scores)


class HybridRetriever:
    def __init__(self, client: QdrantClient | None = None, qdrant_path: Path | None = None) -> None:
        self.client = client or get_qdrant_client(qdrant_path)
        self.embedder = LocalHashEmbedding()

    def _corpus(self) -> list[tuple[str, str, dict[str, Any]]]:
        records: list[tuple[str, str, dict[str, Any]]] = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=COLLECTION_NAME,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = dict(point.payload or {})
                records.append((str(payload["chunk_id"]), str(payload["text"]), payload))
            if offset is None:
                return records

    def search(self, query: str, limit: int = 5, candidate_limit: int = 20) -> list[SearchHit]:
        if not self.client.collection_exists(COLLECTION_NAME):
            return []
        corpus = self._corpus()
        if not corpus:
            return []
        vector_result = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=self.embedder([query])[0],
            limit=min(candidate_limit, len(corpus)),
            with_payload=True,
        ).points
        vector_ids = [str((point.payload or {})["chunk_id"]) for point in vector_result]
        lexical_ids = [chunk_id for chunk_id, _ in BM25Index(corpus).search(query, candidate_limit)]
        fused = reciprocal_rank_fusion([vector_ids, lexical_ids])
        by_id = {chunk_id: (text, payload) for chunk_id, text, payload in corpus}
        vector_ranks = {chunk_id: rank for rank, chunk_id in enumerate(vector_ids, 1)}
        lexical_ranks = {chunk_id: rank for rank, chunk_id in enumerate(lexical_ids, 1)}
        ranked_ids = sorted(fused, key=lambda chunk_id: (-fused[chunk_id], chunk_id))[:limit]
        return [
            SearchHit(
                chunk_id=chunk_id,
                text=by_id[chunk_id][0],
                metadata={key: value for key, value in by_id[chunk_id][1].items() if key != "text"},
                score=fused[chunk_id],
                vector_rank=vector_ranks.get(chunk_id),
                lexical_rank=lexical_ranks.get(chunk_id),
            )
            for chunk_id in ranked_ids
        ]
