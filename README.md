# Telecom Network Incident Triage Agent

This is a **read-only, mock-data-driven** telecom incident triage agent deployed to WSO2 Agent Manager. It accepts the standard Chat Agent contract and generates contextual incident advisories from de-identified mock scenarios.

## Model-backed response design

Version 0.2.0 adds model-backed response synthesis. The service selects the applicable mock incident deterministically, gives only that evidence to the configured LLM, and asks the model to create a contextual advisory. This replaces static preformatted answers while preserving deterministic evidence selection and explicit operational guardrails.

The default runtime model is **Google Gemini** (`gemini-3-flash-preview`). The client uses the OpenAI-compatible Chat Completions protocol and is configurable for **Gemini, Anthropic, OpenAI, or GLM-compatible** endpoints through runtime variables; no source-code change is needed to switch provider or model.

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `gemini` | Informational provider label shown by `/health` and `/status`. |
| `LLM_MODEL` | `gemini-3-flash-preview` | Model identifier to invoke. |
| `LLM_PROVIDER_URL` | `OPENAI_API_BASE` | Platform-managed OpenAI-compatible endpoint. |
| `LLM_PROVIDER_KEY` | `OPENAI_API_KEY` | Platform-managed credential; never logged or committed. |
| `LLM_MAX_TOKENS` | `900` | Visible response token budget, bounded from 128 to 2048. |
| `LLM_HISTORY_MESSAGES` | `6` | Bounded per-session in-memory context. |

For a production platform-hosted Agent Manager deployment, attach a governed LLM service provider. Agent Manager injects `LLM_PROVIDER_URL` and `LLM_PROVIDER_KEY` at runtime. This local Quick Start uses a Kubernetes secret for equivalent secure runtime injection. The actual upstream credential is never included in source code, logs, API responses, or this repository.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Readiness plus safe LLM configuration metadata. |
| `GET /status` | Provider/model, bounded-history, and fallback status. |
| `GET /scenarios` | De-identified mock scenario catalogue. |
| `POST /chat` | Model-synthesized, evidence-grounded incident advisory. |

### Chat request

```json
{
  "message": "Compare the likely causes for the fiber aggregation loss.",
  "session_id": "operator-demo-001",
  "context": {"scenario_id": "fiber-aggregation-loss"}
}
```

The model receives the selected mock scenario and bounded recent history for the supplied `session_id`. It receives neither tool access nor credentials to telecom systems. If the model endpoint is unavailable, the agent returns the existing deterministic mock-data advisory so a safe response remains available.

## Safety boundary

The agent does **not** execute network commands, alter routing, create or close tickets, reserve inventory, send customer communications, or make contractual commitments. It only recommends operator-controlled next steps and names approval gates. All scenarios and related telemetry are synthetic demonstration data.

## Local verification

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
LLM_PROVIDER=gemini LLM_MODEL=gemini-3-flash-preview \
  OPENAI_API_BASE="$OPENAI_API_BASE" OPENAI_API_KEY="$OPENAI_API_KEY" \
  .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```
