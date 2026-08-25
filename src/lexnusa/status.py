from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

KNOWN_STATUSES = {"berlaku", "diubah", "dicabut", "tidak_diketahui"}
STATUS_ALIASES = {
    "berlaku": "berlaku",
    "aktif": "berlaku",
    "diubah": "diubah",
    "perubahan": "diubah",
    "dicabut": "dicabut",
    "tidak berlaku": "dicabut",
    "tidak_berlaku": "dicabut",
    "tidak_diketahui": "tidak_diketahui",
    "": "tidak_diketahui",
}


def normalize_status(value: object) -> str:
    normalized = str(value or "").strip().casefold().replace("-", "_")
    return STATUS_ALIASES.get(normalized, "tidak_diketahui")


def relation_ids(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        values: Iterable[object] = value
    else:
        values = str(value or "").split(",")
    return [str(item).strip() for item in values if str(item).strip()]


def apply_legal_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve explicit and reverse amendment/repeal relations for every indexed chunk."""
    rows = [dict(row) for row in rows]
    document_rows: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    statuses: dict[str, str] = {}
    amended_by: defaultdict[str, set[str]] = defaultdict(set)
    repealed_by: defaultdict[str, set[str]] = defaultdict(set)

    for row in rows:
        document_id = str(row.get("document_id", ""))
        document_rows[document_id].append(row)
        explicit = normalize_status(row.get("status"))
        if explicit != "tidak_diketahui" or document_id not in statuses:
            statuses[document_id] = explicit
        for target in relation_ids(row.get("amends")):
            amended_by[target].add(document_id)
        for target in relation_ids(row.get("repeals")):
            repealed_by[target].add(document_id)

    for document_id in document_rows:
        if repealed_by[document_id]:
            statuses[document_id] = "dicabut"
        elif amended_by[document_id] and statuses.get(document_id) != "dicabut":
            statuses[document_id] = "diubah"

    for document_id, chunks in document_rows.items():
        for row in chunks:
            row["status"] = statuses.get(document_id, "tidak_diketahui")
            row["amended_by"] = ",".join(sorted(amended_by[document_id]))
            row["repealed_by"] = ",".join(sorted(repealed_by[document_id]))
            row["amends"] = ",".join(relation_ids(row.get("amends")))
            row["repeals"] = ",".join(relation_ids(row.get("repeals")))
    return rows


def status_label(metadata: dict[str, object]) -> str:
    status = normalize_status(metadata.get("status"))
    labels = {
        "berlaku": "berlaku",
        "diubah": "telah diubah",
        "dicabut": "telah dicabut/tidak berlaku",
        "tidak_diketahui": "belum terverifikasi",
    }
    detail = ""
    if status == "diubah" and metadata.get("amended_by"):
        detail = f" oleh {metadata['amended_by']}"
    elif status == "dicabut" and metadata.get("repealed_by"):
        detail = f" oleh {metadata['repealed_by']}"
    return labels[status] + detail
