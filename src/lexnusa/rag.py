from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib import request

from lexnusa.agent.router import Route, route_query
from lexnusa.indexing import get_collection
from lexnusa.retrieval.hybrid import HybridRetriever
from lexnusa.retrieval.reranker import CrossEncoderReranker
from lexnusa.status import status_label

DISCLAIMER = "LexNusa adalah alat bantu pencarian, bukan pengganti konsultasi hukum resmi."


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    metadata: dict[str, str | int]
    distance: float


def retrieve_chroma(question: str, chroma_dir: Path, limit: int = 5) -> list[RetrievedChunk]:
    collection = get_collection(chroma_dir)
    count = collection.count()
    if count == 0:
        return []
    result = collection.query(query_texts=[question], n_results=min(limit, count))
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    return [
        RetrievedChunk(text=text, metadata=metadata or {}, distance=float(distance))
        for text, metadata, distance in zip(documents, metadatas, distances)
    ]


def retrieve_qdrant(question: str, qdrant_dir: Path, limit: int = 5, use_reranker: bool = False) -> list[RetrievedChunk]:
    candidate_limit = max(limit * 4, 20)
    hits = HybridRetriever(qdrant_path=qdrant_dir).search(question, limit=candidate_limit, candidate_limit=candidate_limit)
    if use_reranker:
        hits = CrossEncoderReranker().rerank(question, hits, limit=limit)
    else:
        hits = hits[:limit]
    return [RetrievedChunk(text=hit.text, metadata=hit.metadata, distance=1.0 - hit.score) for hit in hits]


def retrieve(
    question: str,
    index_dir: Path,
    limit: int = 5,
    backend: str = "chroma",
    use_reranker: bool = False,
) -> list[RetrievedChunk]:
    plan = route_query(question)
    per_query_limit = max(limit, 5) if plan.route != Route.SIMPLE else limit
    candidates: list[RetrievedChunk] = []
    for query in plan.queries:
        if backend == "qdrant":
            candidates.extend(
                retrieve_qdrant(query, index_dir, limit=per_query_limit, use_reranker=use_reranker)
            )
        else:
            candidates.extend(retrieve_chroma(query, index_dir, limit=per_query_limit))

    deduplicated: dict[str, RetrievedChunk] = {}
    for chunk in candidates:
        key = str(chunk.metadata.get("chunk_id") or (
            chunk.metadata.get("document_id"), chunk.metadata.get("article")
        ))
        current = deduplicated.get(key)
        if current is None or chunk.distance < current.distance:
            deduplicated[key] = chunk
    return sorted(deduplicated.values(), key=lambda chunk: chunk.distance)[:limit]


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    sources = "\n\n".join(
        f"[S{i}] {chunk.metadata['article']} — {chunk.metadata['document_type']} "
        f"No. {chunk.metadata['number']} Tahun {chunk.metadata['year']} "
        f"(status: {status_label(chunk.metadata)})\n{chunk.text}\n"
        f"URL: {chunk.metadata['source_url']}"
        for i, chunk in enumerate(chunks, 1)
    )
    return f"""Anda adalah asisten pencarian hukum Indonesia. Jawab hanya berdasarkan sumber.
Setiap klaim hukum harus memakai penanda [S1], [S2], dan seterusnya. Jelaskan status berlaku,
diubah, atau dicabut hanya dari metadata sumber. Jika status belum terverifikasi, katakan demikian.
Jika sumber tidak cukup, katakan informasi tidak ditemukan. Jangan memberi nasihat hukum profesional.

Pertanyaan: {question}

Sumber:
{sources}
"""


def call_groq(prompt: str, api_key: str, model: str = "llama-3.3-70b-versatile") -> str:
    payload = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0}
    ).encode()
    req = request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=60) as response:
        return json.load(response)["choices"][0]["message"]["content"].strip()


def extractive_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "Informasi tidak ditemukan dalam indeks lokal."
    lines = [f"Hasil penelusuran untuk: {question}"]
    for index, chunk in enumerate(chunks[:3], 1):
        excerpt = " ".join(chunk.text.split())[:500]
        lines.append(f"\n[S{index}] Status: {status_label(chunk.metadata)}. {excerpt}")
    return "".join(lines)


def format_sources(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "Sumber: tidak ada"
    sources = ["Sumber:"]
    for index, chunk in enumerate(chunks, 1):
        meta = chunk.metadata
        sources.append(
            f"- [S{index}] {meta['article']}, {meta['document_type']} No. {meta['number']} "
            f"Tahun {meta['year']} (status: {status_label(meta)}) — {meta['source_url']}"
        )
    return "\n".join(sources)


def answer(
    question: str,
    index_dir: Path,
    use_llm: bool = True,
    backend: str = "chroma",
    use_reranker: bool = False,
) -> str:
    chunks = retrieve(question, index_dir, backend=backend, use_reranker=use_reranker)
    api_key = os.getenv("GROQ_API_KEY")
    body = call_groq(build_prompt(question, chunks), api_key) if use_llm and api_key and chunks else extractive_answer(question, chunks)
    return f"{body}\n\n{format_sources(chunks)}\n\n{DISCLAIMER}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Tanya indeks hukum lokal LexNusa")
    parser.add_argument("question")
    parser.add_argument("--chroma", type=Path, default=Path("data/chroma"))
    parser.add_argument("--qdrant", type=Path, default=Path("data/qdrant"))
    parser.add_argument("--backend", choices=("qdrant", "chroma"), default="qdrant")
    parser.add_argument("--rerank", action="store_true", help="Aktifkan BGE CrossEncoder lokal")
    parser.add_argument("--show-plan", action="store_true", help="Tampilkan route dan subquery retrieval")
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()
    index_dir = args.qdrant if args.backend == "qdrant" else args.chroma
    if args.show_plan:
        plan = route_query(args.question)
        print(f"Route: {plan.route.value}")
        for index, query in enumerate(plan.queries, 1):
            print(f"Q{index}: {query}")
        print()
    print(answer(args.question, index_dir, use_llm=not args.no_llm, backend=args.backend, use_reranker=args.rerank))


if __name__ == "__main__":
    main()
