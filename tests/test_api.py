from pathlib import Path

from fastapi.testclient import TestClient

from lexnusa.api import create_app


def fake_answer(question: str, index_dir: Path, **kwargs: object) -> str:
    return f"Jawaban untuk {question}\n\nSumber:\n- [S1] Pasal 1 — https://peraturan.go.id/contoh.pdf"


def test_health_and_homepage_are_available() -> None:
    client = TestClient(create_app(answer_function=fake_answer))
    assert client.get("/health").json() == {"status": "ok"}
    homepage = client.get("/")
    assert homepage.status_code == 200
    assert "Temukan dasar hukumnya" in homepage.text


def test_chat_returns_answer_and_query_plan(tmp_path: Path) -> None:
    client = TestClient(create_app(answer_function=fake_answer, index_dir=tmp_path))
    response = client.post("/api/chat", json={"question": "Apakah UU ini masih berlaku?", "use_llm": False})

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["route"] == "status"
    assert len(payload["plan"]["queries"]) == 2
    assert "Sumber:" in payload["answer"]


def test_api_key_is_required_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("LEXNUSA_API_KEY", "secret")
    client = TestClient(create_app(answer_function=fake_answer))

    assert client.post("/api/chat", json={"question": "Pertanyaan hukum"}).status_code == 401
    assert client.post(
        "/api/chat",
        json={"question": "Pertanyaan hukum"},
        headers={"X-API-Key": "secret"},
    ).status_code == 200


def test_rate_limit_rejects_excess_requests() -> None:
    client = TestClient(create_app(answer_function=fake_answer, rate_limit=1))
    assert client.post("/api/chat", json={"question": "Pertanyaan pertama"}).status_code == 200
    response = client.post("/api/chat", json={"question": "Pertanyaan kedua"})
    assert response.status_code == 429
