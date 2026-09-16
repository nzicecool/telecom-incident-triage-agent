"""Read-only incident correlation and response formatting for the demo agent."""

from __future__ import annotations

from typing import Any

from mock_data import SCENARIOS, public_scenarios


class ScenarioNotFound(ValueError):
    """Raised when an explicit requested simulation does not exist."""


def _normalise(value: str) -> str:
    return value.lower().replace("_", "-").strip()


def select_scenario(message: str, context: dict[str, Any] | None = None) -> dict:
    """Select a mock case using an explicit context ID or meaningful message terms."""
    context = context or {}
    requested = context.get("scenario_id") or context.get("incident_id")
    if isinstance(requested, str) and requested:
        key = _normalise(requested)
        if key in SCENARIOS:
            return SCENARIOS[key]
        raise ScenarioNotFound(f"No mock scenario matches '{requested}'.")

    text = _normalise(message)
    scored: list[tuple[int, dict]] = []
    for scenario in SCENARIOS.values():
        score = sum(1 for term in scenario["aliases"] if term in text)
        if scenario["id"] in text:
            score += 5
        scored.append((score, scenario))

    score, scenario = max(scored, key=lambda item: item[0])
    if score:
        return scenario
    # The principal demo case is a fiber-aggregation incident.
    return SCENARIOS["fiber-aggregation-loss"]


def list_scenarios_report() -> str:
    entries = [
        "AVAILABLE MOCK INCIDENTS — READ-ONLY DEMONSTRATION",
        "Use a scenario ID in context, or ask to triage the incident by name.",
        "",
    ]
    for scenario in public_scenarios():
        entries.append(
            f"• {scenario['id']} — {scenario['severity']} — {scenario['title']}\n"
            f"  {scenario['summary']}"
        )
    entries.extend(
        [
            "",
            "Examples: 'Triage the fiber aggregation loss' or "
            "context: {\"scenario_id\": \"enterprise-sdwan-latency\"}.",
            "The agent never executes network changes, sends customer messages, or creates tickets.",
        ]
    )
    return "\n".join(entries)


def build_triage_report(scenario: dict) -> str:
    """Produce a grounded incident briefing using only the selected mock data."""
    lines = [
        "NETWORK INCIDENT TRIAGE — READ-ONLY ADVISORY",
        f"Case: {scenario['incident_ref']} | Severity: {scenario['severity']} | Confidence: {scenario['confidence']}%",
        f"Scope: {scenario['region']} | Primary asset: {scenario['primary_asset']} | Start: {scenario['start_time']}",
        "",
        "ASSESSMENT",
        scenario["summary"],
        "",
        "CORRELATED TELEMETRY",
    ]
    lines.extend(
        f"• {alarm['time']} — {alarm['source']}: {alarm['event']}. {alarm['detail']}"
        for alarm in scenario["alarms"]
    )
    lines.extend(["", "LIKELY SERVICE IMPACT"])
    lines.extend(
        f"• {service['service']} — {service['customer']} ({service['class']}, {service['sla']}): {service['impact']}"
        for service in scenario["affected_services"]
    )
    lines.extend(["", "CHANGE CONTEXT", scenario["change_context"], "", "ROOT-CAUSE HYPOTHESES"])
    lines.extend(
        f"{hypothesis['rank']}. {hypothesis['cause']} — {hypothesis['confidence']}% confidence. "
        f"Evidence: {hypothesis['evidence']}"
        for hypothesis in scenario["hypotheses"]
    )
    historical = scenario["historical"]
    lines.extend(
        [
            "",
            "SIMILAR RESOLVED INCIDENT",
            f"• {historical['reference']} — {historical['similarity']}% similarity. {historical['outcome']}",
            "",
            "RECOMMENDED OPERATOR-CONTROLLED NEXT STEPS",
        ]
    )
    lines.extend(f"{index}. {step}" for index, step in enumerate(scenario["runbook"], start=1))
    lines.extend(
        [
            "",
            "DRAFT TICKET UPDATE — NOT SUBMITTED",
            scenario["ticket_draft"],
            "",
            "APPROVAL GATES",
        ]
    )
    lines.extend(f"• {gate}" for gate in scenario["approval_gates"])
    lines.extend(
        [
            "",
            "SAFETY BOUNDARY",
            "This simulation is advisory only. It does not execute network commands, alter routing, create or close tickets, reserve inventory, or send customer communications.",
        ]
    )
    return "\n".join(lines)


def answer(message: str, context: dict[str, Any] | None = None) -> str:
    """Handle a user request with a bounded deterministic response."""
    query = _normalise(message)
    if any(term in query for term in ("help", "list", "scenario", "mock data", "available")):
        return list_scenarios_report()
    try:
        return build_triage_report(select_scenario(message, context))
    except ScenarioNotFound as error:
        return f"{error}\n\n{list_scenarios_report()}"
