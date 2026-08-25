from pathlib import Path

from lexnusa.indexing import get_collection
from lexnusa.rag import DISCLAIMER, answer


def test_answer_always_includes_article_link_and_disclaimer(tmp_path: Path) -> None:
    collection = get_collection(tmp_path)
    collection.add(
        ids=["uu-1-2024:pasal-1"],
        documents=["Pasal 1\nSetiap orang berhak membaca dokumen publik."],
        metadatas=[{
            "document_id": "uu-1-2024",
            "article": "Pasal 1",
            "title": "Peraturan Contoh",
            "document_type": "UU",
            "number": "1",
            "year": 2024,
            "source_url": "https://peraturan.go.id/files/contoh.pdf",
        }],
    )

    result = answer("Apa hak setiap orang?", tmp_path, use_llm=False)

    assert "Pasal 1" in result
    assert "https://peraturan.go.id/files/contoh.pdf" in result
    assert DISCLAIMER in result


def test_empty_index_refuses_to_invent_answer(tmp_path: Path) -> None:
    result = answer("Apa hukum yang berlaku?", tmp_path, use_llm=False)
    assert "Informasi tidak ditemukan" in result
    assert DISCLAIMER in result


def test_answer_reports_unverified_legal_status(tmp_path: Path) -> None:
    collection = get_collection(tmp_path)
    collection.add(
        ids=["uu-1-2024:pasal-1"],
        documents=["Pasal 1\nKetentuan contoh."],
        metadatas=[{
            "document_id": "uu-1-2024",
            "article": "Pasal 1",
            "title": "Peraturan Contoh",
            "document_type": "UU",
            "number": "1",
            "year": 2024,
            "source_url": "https://peraturan.go.id/files/contoh.pdf",
            "status": "tidak_diketahui",
        }],
    )

    result = answer("Apakah UU ini masih berlaku?", tmp_path, use_llm=False)
    assert "status: belum terverifikasi" in result.casefold()
