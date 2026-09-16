# Telecom Network Incident Triage and Resolution Coordinator

This repository contains a **read-only, deterministic demonstration agent** for WSO2 Agent Manager. It simulates a Network Operations Center (NOC) workflow: the agent correlates telecom alarms, service topology, change context, historical incidents, and a runbook to create an operator-ready incident brief.

The agent exposes the WSO2 Agent Manager **Chat Agent** contract on port `8000`:

```text
POST /chat
{
  "message": "Triage the fiber aggregation loss",
  "session_id": "optional-session-id",
  "context": {"scenario_id": "optional-scenario-id"}
}
```

The response is:

```json
{"response": "...incident briefing..."}
```

## Demonstration data

All organizations, services, alarms, timestamps, and incident identifiers are mock and de-identified. The available scenarios are:

| Scenario ID | Incident | Expected focus |
|---|---|---|
| `fiber-aggregation-loss` | Optical and transport loss at a metro aggregation point | Service impact, likely fiber impairment, outside-plant dispatch recommendation |
| `mobile-ran-congestion` | Event-driven 5G radio congestion | Capacity-risk evidence and engineer-controlled mitigation assessment |
| `enterprise-sdwan-latency` | Latency and packet loss on a cloud interconnect | Premium SLA risk and approved traffic-balancing assessment |

Send `help`, `list scenarios`, or `show mock data` to retrieve the in-agent scenario guide. The service also provides `GET /scenarios` and `GET /health` endpoints for deployment validation.

## Safety boundary

This agent is intentionally advisory only. It **does not** execute network commands, alter routing, create or close tickets, reserve inventory, send customer communications, or make contractual commitments. Every report identifies the approval gates required before such actions can happen.

## Local run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000/docs`, or make a request:

```bash
curl -sS http://localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"message":"Triage the fiber aggregation loss"}'
```

## WSO2 Agent Manager deployment settings

Create a **Platform-Hosted Agent** from source code and provide the following values:

| Setting | Value |
|---|---|
| Repository | This repository |
| Branch | `main` |
| Project Path | `/` |
| Build Type | Python |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port 8000` |
| Python Version | 3.11 |
| Agent Type | Chat Agent |
| Port | 8000 |
| Auto instrumentation | Enabled when an AMP-compatible Python 3.11 instrumentation image is available |

Use the Agent Manager Test view after deployment with `Triage the fiber aggregation loss`. The expected report contains `SIM-SP-2026-0916-017`, `AGG-BKK-17`, a service-impact list, root-cause hypotheses, an unsubmitted ticket draft, and the explicit read-only safety boundary.
