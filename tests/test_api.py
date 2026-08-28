import json
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


def test_multiple_invite_keys_are_each_individually_valid(monkeypatch) -> None:
    monkeypatch.delenv("LEXNUSA_API_KEY", raising=False)
    monkeypatch.setenv("LEXNUSA_API_KEYS", "tester-a, tester-b")
    client = TestClient(create_app(answer_function=fake_answer))

    assert client.post("/api/chat", json={"question": "Pertanyaan hukum"}).status_code == 401
    assert client.post(
        "/api/chat", json={"question": "Pertanyaan hukum"}, headers={"X-API-Key": "tester-b"}
    ).status_code == 200
    assert client.post(
        "/api/chat", json={"question": "Pertanyaan hukum"}, headers={"X-API-Key": "unknown"}
    ).status_code == 401


def test_feedback_is_appended_to_configured_file(tmp_path: Path) -> None:
    feedback_file = tmp_path / "feedback.jsonl"
    client = TestClient(create_app(answer_function=fake_answer, feedback_file=feedback_file))

    response = client.post(
        "/api/feedback",
        json={"question": "Apa itu LexNusa?", "answer": "Asisten regulasi.", "relevant": True},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "recorded"}
    lines = feedback_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["question"] == "Apa itu LexNusa?"
    assert record["relevant"] is True
    assert "timestamp" in record


def test_feedback_requires_api_key_when_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LEXNUSA_API_KEY", "secret")
    client = TestClient(create_app(answer_function=fake_answer, feedback_file=tmp_path / "feedback.jsonl"))

    response = client.post(
        "/api/feedback",
        json={"question": "Pertanyaan", "answer": "Jawaban", "relevant": False},
    )

    assert response.status_code == 401
