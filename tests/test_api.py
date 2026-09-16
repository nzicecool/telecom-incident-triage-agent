from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_reports_ready():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_scenarios_are_explicitly_simulated_and_read_only():
    response = client.get("/scenarios")
    assert response.status_code == 200
    payload = response.json()
    assert payload["simulation"] is True
    assert payload["read_only"] is True
    assert len(payload["scenarios"]) == 3


def test_fiber_triage_is_grounded_and_safe():
    response = client.post(
        "/chat",
        json={"message": "Triage the fiber aggregation loss", "session_id": "demo-001"},
    )
    assert response.status_code == 200
    result = response.json()["response"]
    assert "SIM-SP-2026-0916-017" in result
    assert "AGG-BKK-17" in result
    assert "Eastbank Financial Services" in result
    assert "READ-ONLY ADVISORY" in result
    assert "does not execute network commands" in result


def test_context_selects_the_requested_scenario():
    response = client.post(
        "/chat",
        json={
            "message": "Please prepare an incident brief.",
            "context": {"scenario_id": "enterprise-sdwan-latency"},
        },
    )
    assert response.status_code == 200
    result = response.json()["response"]
    assert "SIM-SP-2026-0916-029" in result
    assert "Orbit Retail Group" in result


def test_invalid_scenario_falls_back_to_safe_guidance():
    response = client.post(
        "/chat",
        json={"message": "triage", "context": {"scenario_id": "not-a-real-case"}},
    )
    assert response.status_code == 200
    assert "No mock scenario matches" in response.json()["response"]
