from lexnusa.models import DocumentMetadata
from lexnusa.parsing import chunk_articles


def metadata() -> DocumentMetadata:
    return DocumentMetadata(
        document_id="uu-1-2024",
        document_type="UU",
        number="1",
        year=2024,
        title="Peraturan Contoh",
        detail_url="https://peraturan.go.id/id/contoh",
        source_url="https://peraturan.go.id/files/contoh.pdf",
    )


def test_chunk_articles_keeps_article_boundaries_and_citations() -> None:
    text = "PEMBUKAAN\nPasal 1\nSetiap orang berhak membaca.\nPasal 2\nKetentuan berlaku umum."
    chunks = chunk_articles(text, metadata())

    assert [chunk.article for chunk in chunks] == ["Pasal 1", "Pasal 2"]
    assert "Setiap orang" in chunks[0].text
    assert chunks[0].source_url.endswith("contoh.pdf")


def test_chunk_articles_returns_empty_when_pdf_has_no_articles() -> None:
    assert chunk_articles("Lampiran tanpa struktur pasal", metadata()) == []

