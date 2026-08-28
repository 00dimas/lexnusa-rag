from pathlib import Path

from lexnusa.eval import GoldenCase, load_golden_set, run_case, run_eval, summarize

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_bundled_golden_set_loads_and_passes(tmp_path: Path) -> None:
    golden_path = REPO_ROOT / "eval" / "golden_qa.jsonl"
    cases = load_golden_set(golden_path)
    assert len(cases) >= 5

    results = run_eval(golden_path, tmp_path)
    summary = summarize(results)

    assert summary["total"] == len(cases)
    assert summary["passed"] == summary["total"]
    assert summary["retrieval_hit_rate"] == 1.0
    assert summary["keyword_hit_rate"] == 1.0


def test_run_case_flags_missing_expected_source(tmp_path: Path) -> None:
    case = GoldenCase(
        id="gq-missing",
        question="Apa ketentuan yang tidak ada dalam indeks?",
        documents=[
            {
                "document_id": "uu-99-2099",
                "article": "Pasal 1",
                "title": "Dokumen Lain",
                "document_type": "UU",
                "number": "99",
                "year": 2099,
                "source_url": "https://peraturan.go.id/files/lain.pdf",
                "text": "Pasal 1\nKetentuan yang tidak relevan dengan pertanyaan.",
            }
        ],
        expected_document_id="uu-1-2024",
        expected_article="Pasal 1",
        expected_keywords=("frasa yang tidak akan pernah muncul",),
    )

    result = run_case(case, tmp_path)

    assert result.retrieval_hit is False
    assert result.keyword_hit is False
    assert result.passed is False
