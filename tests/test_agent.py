from lexnusa.agent.router import Route, route_query
from lexnusa.status import apply_legal_status, status_label


def test_router_uses_single_retrieval_for_simple_question() -> None:
    plan = route_query("Apa syarat perlindungan saksi?")
    assert plan.route == Route.SIMPLE
    assert plan.queries == ("Apa syarat perlindungan saksi?",)


def test_router_expands_complex_comparison() -> None:
    plan = route_query("Bandingkan perlindungan saksi dan perlindungan korban dalam undang-undang")
    assert plan.route == Route.COMPLEX
    assert len(plan.queries) > 1


def test_router_expands_status_question() -> None:
    plan = route_query("Apakah UU Nomor 1 Tahun 2020 masih berlaku?")
    assert plan.route == Route.STATUS
    assert "mencabut" in plan.queries[1]


def test_reverse_relations_update_legal_status() -> None:
    rows = [
        {"chunk_id": "old:1", "document_id": "uu-1-2020", "status": "berlaku"},
        {
            "chunk_id": "amendment:1",
            "document_id": "uu-2-2022",
            "status": "berlaku",
            "amends": "uu-1-2020",
        },
        {
            "chunk_id": "repeal:1",
            "document_id": "uu-3-2024",
            "status": "berlaku",
            "repeals": "uu-1-2020",
        },
    ]

    resolved = apply_legal_status(rows)
    old = resolved[0]
    assert old["status"] == "dicabut"
    assert old["amended_by"] == "uu-2-2022"
    assert old["repealed_by"] == "uu-3-2024"
    assert status_label(old) == "telah dicabut/tidak berlaku oleh uu-3-2024"
