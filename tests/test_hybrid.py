from __future__ import annotations

import json
from pathlib import Path

from lexnusa.qdrant_store import get_qdrant_client, index_qdrant
from lexnusa.rag import DISCLAIMER, answer
from lexnusa.retrieval.hybrid import BM25Index, HybridRetriever, reciprocal_rank_fusion
from lexnusa.retrieval.reranker import CrossEncoderReranker


def rows() -> list[dict[str, str | int]]:
    common = {
        "document_id": "uu-1-2024",
        "title": "Peraturan Contoh",
        "document_type": "UU",
        "number": "1",
        "year": 2024,
        "source_url": "https://peraturan.go.id/files/contoh.pdf",
    }
    return [
        {**common, "chunk_id": "doc:pasal-1", "article": "Pasal 1", "text": "Pasal 1 perlindungan saksi dan korban"},
        {**common, "chunk_id": "doc:pasal-2", "article": "Pasal 2", "text": "Pasal 2 ketentuan anggaran negara"},
    ]


def test_bm25_prioritizes_exact_legal_terms() -> None:
    documents = [(row["chunk_id"], row["text"], row) for row in rows()]
    assert BM25Index(documents).search("perlindungan saksi", 2)[0][0] == "doc:pasal-1"


def test_rrf_rewards_results_present_in_both_rankings() -> None:
    scores = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
    assert scores["b"] > scores["a"]


def test_qdrant_hybrid_search_end_to_end(tmp_path: Path) -> None:
    processed = tmp_path / "articles.jsonl"
    processed.write_text("\n".join(json.dumps(row) for row in rows()), encoding="utf-8")
    assert index_qdrant(processed, tmp_path / "qdrant") == 2

    hits = HybridRetriever(client=get_qdrant_client(tmp_path / "qdrant")).search("perlindungan saksi", limit=2)
    assert hits[0].chunk_id == "doc:pasal-1"
    assert hits[0].lexical_rank == 1
    assert hits[0].metadata["source_url"].endswith("contoh.pdf")


def test_qdrant_answer_keeps_citations_and_disclaimer(tmp_path: Path) -> None:
    processed = tmp_path / "articles.jsonl"
    processed.write_text("\n".join(json.dumps(row) for row in rows()), encoding="utf-8")
    index_qdrant(processed, tmp_path / "qdrant")

    result = answer(
        "Apa ketentuan perlindungan saksi?",
        tmp_path / "qdrant",
        use_llm=False,
        backend="qdrant",
    )

    assert "Pasal 1" in result
    assert "https://peraturan.go.id/files/contoh.pdf" in result
    assert DISCLAIMER in result


class FakeCrossEncoder:
    def predict(self, pairs, **kwargs):
        return [0.1 if "saksi" in text else 0.9 for _, text in pairs]


def test_cross_encoder_reranks_candidates() -> None:
    documents = [(row["chunk_id"], row["text"], row) for row in rows()]
    from lexnusa.retrieval.hybrid import SearchHit

    hits = [SearchHit(chunk_id=chunk_id, text=text, metadata=payload, score=0.5) for chunk_id, text, payload in documents]
    reranked = CrossEncoderReranker(model=FakeCrossEncoder()).rerank("anggaran", hits)
    assert reranked[0].chunk_id == "doc:pasal-2"
    assert reranked[0].rerank_score == 0.9
