from pathlib import Path

from lexnusa.scraping.peraturan import PeraturanScraper


def test_parse_listing_extracts_official_metadata(tmp_path: Path) -> None:
    html = Path("tests/fixtures/listing.html").read_text(encoding="utf-8")
    with PeraturanScraper(tmp_path, delay_seconds=1) as scraper:
        documents = scraper.parse_listing(html)

    assert len(documents) == 1
    document = documents[0]
    assert document.document_id == "uu-12-2024"
    assert document.title == "Kabupaten Contoh"
    assert document.source_url == "https://peraturan.go.id/files/uu-no-12-tahun-2024.pdf"


def test_parse_detail_extracts_status_and_relations(tmp_path: Path) -> None:
    html = """
    <dl><dt>Status</dt><dd>Berlaku</dd></dl>
    <div>Mengubah <a href="/id/uu-1-2020">Undang-Undang Nomor 1 Tahun 2020</a></div>
    <div>Mencabut <a href="/id/pp-2-2019">Peraturan Pemerintah Nomor 2 Tahun 2019</a></div>
    """
    with PeraturanScraper(tmp_path, delay_seconds=1) as scraper:
        metadata = scraper.parse_detail_metadata(html)

    assert metadata == {
        "status": "berlaku",
        "amends": "uu-1-2020",
        "repeals": "pp-2-2019",
    }
