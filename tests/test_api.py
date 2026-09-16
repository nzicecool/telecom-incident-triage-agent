from dataclasses import replace

from fastapi.testclient import TestClient

from llm_triage import LLMSettings, ModelUnavailable, TelecomLLMTriage
from main import app, triage

client = TestClient(app)


class FakeCompletion:
    class Choice:
        class Message:
            content = (
                "## Assessment\n"
                "The evidence supports a physical fiber impairment hypothesis."
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


class FakeAnthropicCompletion:
    class Block:
        type = "text"
        text = "## Assessment\nThe evidence supports a fiber impairment hypothesis."

    content = [Block()]


class FakeAnthropicClient:
    class Messages:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return FakeAnthropicCompletion()

    def __init__(self) -> None:
        self.messages = self.Messages()


def test_health_reports_ready_without_secrets():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "api_key" not in str(payload).lower()
    assert payload["llm"]["model"]
    assert payload["llm"]["provider"] == "gemini"
    assert set(payload["llm"]["supported_providers"]) == {"gemini", "anthropic", "openai", "glm"}


def test_scenarios_are_explicitly_simulated_and_read_only():
    response = client.get("/scenarios")
    assert response.status_code == 200
    payload = response.json()
    assert payload["simulation"] is True
    assert payload["read_only"] is True
    assert len(payload["scenarios"]) == 3


def test_model_synthesis_is_grounded_keeps_history_and_exposes_safe_steps(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(triage, "_get_openai_client", lambda: fake_client)

    first = client.post(
        "/chat",
        json={"message": "Triage the fiber aggregation loss", "session_id": "demo-llm"},
    )
    second = client.post(
        "/chat",
        json={"message": "What should the operator verify first?", "session_id": "demo-llm"},
    )

    assert first.status_code == 200
    first_payload = first.json()
    assert "Safety boundary" in first_payload["response"]
    assert "No network command" in first_payload["response"]
    assert first_payload["provider"] == "gemini"
    assert first_payload["used_fallback"] is False
    assert len(first_payload["development_steps"]) == 4
    assert all("reasoning" not in step.lower() for step in first_payload["development_steps"])
    assert second.status_code == 200
    assert len(fake_client.chat.completions.calls) == 2
    latest_messages = fake_client.chat.completions.calls[-1]["messages"]
    assert any(message["content"] == "Triage the fiber aggregation loss" for message in latest_messages)
    evidence_message = latest_messages[-1]["content"]
    assert "SIM-SP-2026-0916-017" in evidence_message
    assert "AGG-BKK-17" in evidence_message
    assert fake_client.chat.completions.calls[-1]["model"]


def test_native_anthropic_provider_uses_messages_api_and_history(monkeypatch):
    settings = LLMSettings(
        provider="anthropic",
        model="claude-test-model",
        base_url="https://api.anthropic.com",
        api_key="test-key",
        max_tokens=300,
        history_messages=4,
    )
    service = TelecomLLMTriage(settings)
    fake_client = FakeAnthropicClient()
    monkeypatch.setattr(service, "_get_anthropic_client", lambda: fake_client)

    result = service.answer_with_metadata(
        "Triage the fiber aggregation loss", {"scenario_id": "fiber-aggregation-loss"}, "anthropic-demo"
    )

    assert result.provider == "anthropic"
    assert result.used_fallback is False
    assert "Safety boundary" in result.response
    request = fake_client.messages.calls[0]
    assert request["model"] == "claude-test-model"
    assert request["system"]
    assert request["messages"][-1]["role"] == "user"
    assert "SIM-SP-2026-0916-017" in request["messages"][-1]["content"]


def test_provider_alias_normalization_and_protocols():
    assert LLMSettings.from_environment().provider == "gemini"
    glm = replace(LLMSettings.from_environment(), provider="glm")
    anthropic = replace(LLMSettings.from_environment(), provider="anthropic")
    assert glm.protocol == "openai-chat-completions"
    assert anthropic.protocol == "anthropic-messages"


def test_model_outage_uses_grounded_deterministic_fallback(monkeypatch):
    def unavailable(*args, **kwargs):
        raise ModelUnavailable("offline")

    monkeypatch.setattr(triage, "_generate", unavailable)
    response = client.post(
        "/chat",
        json={"message": "Triage the fiber aggregation loss", "session_id": "fallback-case"},
    )
    assert response.status_code == 200
    payload = response.json()
    result = payload["response"]
    assert "SIM-SP-2026-0916-017" in result
    assert "AGG-BKK-17" in result
    assert "READ-ONLY ADVISORY" in result
    assert "does not execute network commands" in result
    assert payload["used_fallback"] is True
    assert payload["provider"] is None


def test_context_selects_the_requested_scenario_for_llm_grounding(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(triage, "_get_openai_client", lambda: fake_client)
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
    monkeypatch.setattr(triage, "_get_openai_client", lambda: fake_client)
    response = client.post(
        "/chat",
        json={"message": "triage", "context": {"scenario_id": "not-a-real-case"}},
    )
    assert response.status_code == 200
    assert "No mock scenario matches" in response.json()["response"]
    assert not fake_client.chat.completions.calls


def test_custom_console_exposes_safe_left_panel():
    response = client.get("/console")
    assert response.status_code == 200
    assert "Development steps" in response.text
    assert "not private model reasoning" in response.text
