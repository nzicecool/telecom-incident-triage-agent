from fastapi.testclient import TestClient

from llm_triage import ModelUnavailable
from main import app, triage

client = TestClient(app)


class FakeCompletion:
    class Choice:
        class Message:
            content = (
                "## Assessment\n"
                "The evidence supports a physical fiber impairment hypothesis.\n\n"
                "## Safety boundary\n"
                "This is a read-only simulation; no network action was performed."
            )

        message = Message()

    choices = [Choice()]


class FakeClient:
    class Chat:
        class Completions:
            def __init__(self) -> None:
                self.calls: list[dict] = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return FakeCompletion()

        def __init__(self) -> None:
            self.completions = self.Completions()

    def __init__(self) -> None:
        self.chat = self.Chat()


def test_health_reports_ready_without_secrets():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "api_key" not in str(payload).lower()
    assert payload["llm"]["model"]


def test_scenarios_are_explicitly_simulated_and_read_only():
    response = client.get("/scenarios")
    assert response.status_code == 200
    payload = response.json()
    assert payload["simulation"] is True
    assert payload["read_only"] is True
    assert len(payload["scenarios"]) == 3


def test_model_synthesis_is_grounded_and_keeps_session_history(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(triage, "_get_client", lambda: fake_client)

    first = client.post(
        "/chat",
        json={"message": "Triage the fiber aggregation loss", "session_id": "demo-llm"},
    )
    second = client.post(
        "/chat",
        json={"message": "What should the operator verify first?", "session_id": "demo-llm"},
    )

    assert first.status_code == 200
    assert "Safety boundary" in first.json()["response"]
    assert "No network command" in first.json()["response"]
    assert second.status_code == 200
    assert len(fake_client.chat.completions.calls) == 2
    latest_messages = fake_client.chat.completions.calls[-1]["messages"]
    assert any(message["content"] == "Triage the fiber aggregation loss" for message in latest_messages)
    evidence_message = latest_messages[-1]["content"]
    assert "SIM-SP-2026-0916-017" in evidence_message
    assert "AGG-BKK-17" in evidence_message
    assert fake_client.chat.completions.calls[-1]["model"]


def test_model_outage_uses_grounded_deterministic_fallback(monkeypatch):
    def unavailable(*args, **kwargs):
        raise ModelUnavailable("offline")

    monkeypatch.setattr(triage, "_generate", unavailable)
    response = client.post(
        "/chat",
        json={"message": "Triage the fiber aggregation loss", "session_id": "fallback-case"},
    )
    assert response.status_code == 200
    result = response.json()["response"]
    assert "SIM-SP-2026-0916-017" in result
    assert "AGG-BKK-17" in result
    assert "READ-ONLY ADVISORY" in result
    assert "does not execute network commands" in result


def test_context_selects_the_requested_scenario_for_llm_grounding(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(triage, "_get_client", lambda: fake_client)
    response = client.post(
        "/chat",
        json={
            "message": "Prepare a concise risk briefing.",
            "context": {"scenario_id": "enterprise-sdwan-latency"},
        },
    )
    assert response.status_code == 200
    evidence = fake_client.chat.completions.calls[-1]["messages"][-1]["content"]
    assert "SIM-SP-2026-0916-029" in evidence
    assert "Orbit Retail Group" in evidence


def test_invalid_scenario_returns_safe_guidance_without_model_call(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(triage, "_get_client", lambda: fake_client)
    response = client.post(
        "/chat",
        json={"message": "triage", "context": {"scenario_id": "not-a-real-case"}},
    )
    assert response.status_code == 200
    assert "No mock scenario matches" in response.json()["response"]
    assert not fake_client.chat.completions.calls
