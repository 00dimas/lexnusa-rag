from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from lexnusa.indexing import get_collection
from lexnusa.rag import answer, retrieve


@dataclass(frozen=True)
class GoldenCase:
    id: str
    question: str
    documents: list[dict[str, object]]
    expected_document_id: str
    expected_article: str
    expected_keywords: tuple[str, ...]


@dataclass(frozen=True)
class EvalResult:
    id: str
    question: str
    retrieval_hit: bool
    keyword_hit: bool
    answer_text: str

    @property
    def passed(self) -> bool:
        return self.retrieval_hit and self.keyword_hit


def load_golden_set(path: Path) -> list[GoldenCase]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        cases.append(
            GoldenCase(
                id=row["id"],
                question=row["question"],
                documents=row["documents"],
                expected_document_id=row["expected_document_id"],
                expected_article=row["expected_article"],
                expected_keywords=tuple(kw.casefold() for kw in row.get("expected_keywords", [])),
            )
        )
    return cases


def _index_case_documents(index_dir: Path, case: GoldenCase) -> None:
    collection = get_collection(index_dir)
    collection.add(
        ids=[f"{case.id}:{i}" for i in range(len(case.documents))],
        documents=[str(doc["text"]) for doc in case.documents],
        metadatas=[{key: value for key, value in doc.items() if key != "text"} for doc in case.documents],
    )


def run_case(case: GoldenCase, index_root: Path) -> EvalResult:
    """Index the case's own reference documents, then score retrieval and the final answer.

    Each case carries its own source documents so the golden set stays reproducible offline,
    independent of whatever has (or hasn't) been scraped into a real index.
    """
    index_dir = index_root / case.id
    index_dir.mkdir(parents=True, exist_ok=True)
    _index_case_documents(index_dir, case)

    chunks = retrieve(case.question, index_dir, backend="chroma")
    retrieval_hit = any(
        chunk.metadata.get("document_id") == case.expected_document_id
        and chunk.metadata.get("article") == case.expected_article
        for chunk in chunks
    )

    answer_text = answer(case.question, index_dir, use_llm=False, backend="chroma")
    lowered = answer_text.casefold()
    keyword_hit = all(keyword in lowered for keyword in case.expected_keywords)

    return EvalResult(
        id=case.id,
        question=case.question,
        retrieval_hit=retrieval_hit,
        keyword_hit=keyword_hit,
        answer_text=answer_text,
    )


def run_eval(golden_path: Path, index_root: Path) -> list[EvalResult]:
    return [run_case(case, index_root) for case in load_golden_set(golden_path)]


def summarize(results: list[EvalResult]) -> dict[str, object]:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    retrieval_hits = sum(1 for r in results if r.retrieval_hit)
    keyword_hits = sum(1 for r in results if r.keyword_hit)
    return {
        "total": total,
        "passed": passed,
        "pass_rate": passed / total if total else 0.0,
        "retrieval_hit_rate": retrieval_hits / total if total else 0.0,
        "keyword_hit_rate": keyword_hits / total if total else 0.0,
        "cases": [
            {
                "id": result.id,
                "question": result.question,
                "retrieval_hit": result.retrieval_hit,
                "keyword_hit": result.keyword_hit,
                "passed": result.passed,
            }
            for result in results
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LexNusa golden QA evaluation offline")
    parser.add_argument("--golden", type=Path, default=Path("eval/golden_qa.jsonl"))
    parser.add_argument("--index-root", type=Path, default=Path("data/eval-index"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    summary = summarize(run_eval(args.golden, args.index_root))
    report = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    print(report)

    if summary["passed"] != summary["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
