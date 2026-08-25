from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from lexnusa.retrieval.hybrid import SearchHit


class PairScorer(Protocol):
    def predict(self, pairs: list[tuple[str, str]], **kwargs: object): ...


class CrossEncoderReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", model: PairScorer | None = None) -> None:
        if model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError('Instal reranker dengan: pip install -e ".[rerank]"') from exc
            model = CrossEncoder(model_name, max_length=512)
        self.model = model

    def rerank(self, query: str, hits: list[SearchHit], limit: int = 5) -> list[SearchHit]:
        if not hits:
            return []
        scores = self.model.predict([(query, hit.text) for hit in hits], batch_size=16, show_progress_bar=False)
        scored = [replace(hit, rerank_score=float(score)) for hit, score in zip(hits, scores)]
        return sorted(scored, key=lambda hit: (-(hit.rerank_score or 0.0), -hit.score, hit.chunk_id))[:limit]
