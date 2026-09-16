# Telecom Network Incident Triage Agent

This is a **read-only, mock-data-driven** telecom incident triage agent deployed to WSO2 Agent Manager. It accepts the standard Chat Agent contract and generates contextual incident advisories from de-identified mock scenarios.

## Model-backed response design

Version 0.3.0 selects the applicable mock incident deterministically, gives only that evidence to the configured model, and asks the model to create a contextual advisory. This replaces static preformatted answers while preserving deterministic evidence selection, bounded session context, and explicit operational guardrails.

**Google Gemini remains the default provider** (`gemini-3-flash-preview`). The application is provider-configurable at runtime: Gemini, OpenAI, and Z.ai/GLM use the OpenAI-compatible Chat Completions protocol, while Anthropic uses the native Messages API. No source-code change is required to switch among approved providers.

| Environment variable | Gemini/OpenAI/GLM behavior | Anthropic behavior |
| --- | --- | --- |
| `LLM_PROVIDER` | `gemini` (default), `openai`, or `glm` | `anthropic` |
| `LLM_MODEL` | Default: `gemini-3-flash-preview` | Set an approved Claude model identifier. |
| `LLM_PROVIDER_URL` | An OpenAI-compatible API base URL | Anthropic API base URL; defaults to `https://api.anthropic.com`. |
| `LLM_PROVIDER_KEY` | Platform-managed provider credential | Platform-managed Anthropic credential. |
| `LLM_MAX_TOKENS` | Default `900`, bounded from 128 to 2048 | Same. |
| `LLM_HISTORY_MESSAGES` | Default `6`, bounded from 0 to 12 | Same. |

For a production platform-hosted Agent Manager deployment, attach a governed LLM service provider. Agent Manager injects `LLM_PROVIDER_URL` and `LLM_PROVIDER_KEY` at runtime. This local Quick Start uses a Kubernetes secret for equivalent secure runtime injection. The actual upstream credential is never included in source code, logs, API responses, or this repository.

## Endpoints and user interfaces

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Readiness plus safe provider/model metadata. |
| `GET /status` | Provider, bounded-history, fallback, and custom-console status. |
| `GET /scenarios` | De-identified mock scenario catalogue. |
| `POST /chat` | Model-synthesized, evidence-grounded incident advisory. |
| `GET /console` | Optional standalone console with a **left-side development-step panel**. |

`POST /chat` returns the standard `response` string plus `development_steps`, `provider`, and `used_fallback`. Development steps are **safe workflow milestones**—for example, selecting synthetic evidence or applying a read-only boundary—not private chain-of-thought or model reasoning. Agent Manager’s built-in Try It interface renders the standard response; the optional `/console` page renders these safe milestones in a left panel.

### Chat request

```json
{
  "message": "Compare the likely causes for the fiber aggregation loss.",
  "session_id": "operator-demo-001",
  "context": {"scenario_id": "fiber-aggregation-loss"}
}
```

The model receives the selected mock scenario and bounded recent history for the supplied `session_id`. It receives neither tool access nor credentials to telecom systems. If the model endpoint is unavailable, the agent returns the deterministic mock-data advisory and marks `used_fallback` as `true`.

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
