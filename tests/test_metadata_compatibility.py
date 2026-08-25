import json
from pathlib import Path

from lexnusa.models import DocumentMetadata


def test_m3_metadata_remains_compatible_with_m4_defaults(tmp_path: Path) -> None:
    payload = {
        "document_id": "uu-1-2024",
        "document_type": "UU",
        "number": "1",
        "year": 2024,
        "title": "Peraturan Contoh",
        "detail_url": "https://peraturan.go.id/id/contoh",
        "source_url": "https://peraturan.go.id/files/contoh.pdf",
        "pdf_path": str(tmp_path / "contoh.pdf"),
    }
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")

    allowed = DocumentMetadata.__dataclass_fields__.keys()
    metadata = DocumentMetadata(**{key: payload[key] for key in allowed if key in payload})

    assert metadata.status == "tidak_diketahui"
    assert metadata.amends == ""
    assert metadata.repeals == ""
