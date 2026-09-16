# Telecom Incident Triage Agent — LLM Integration Handover

## Deployment outcome

The **Telecom Network Incident Triage** agent is deployed in WSO2 Agent Manager with model-backed response synthesis. Build `telco-incident-triage-1789569374930` is active from source commit `5403d2c` in the private repository [`nzicecool/telecom-incident-triage-agent`](https://github.com/nzicecool/telecom-incident-triage-agent). A follow-on source update adds native Anthropic support, safe development-step metadata, and a standalone left-panel console; it is verified locally and ready for the next rebuild.

**Google Gemini remains the default** (`gemini-3-flash-preview`). The adapter supports Gemini, Anthropic, OpenAI, and Z.ai/GLM according to the current runtime configuration. Gemini, OpenAI, and GLM use OpenAI-compatible Chat Completions; Anthropic uses its native Messages API.

| Runtime setting | Gemini default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `gemini` | `gemini`, `anthropic`, `openai`, or `glm`. |
| `LLM_MODEL` | `gemini-3-flash-preview` | Selected provider’s model identifier. |
| `LLM_PROVIDER_URL` | OpenAI-compatible Manus model gateway | Selected provider’s endpoint. |
| `LLM_MAX_TOKENS` | `900` | Bounded visible-response budget. |
| `LLM_HISTORY_MESSAGES` | `6` | Bounded in-memory context per chat session. |
| `LLM_PROVIDER_KEY` | Kubernetes `secretKeyRef` | Runtime credential; no value is stored in source. |

## Agent behavior

The application first chooses the mock incident deterministically, then supplies only the selected de-identified evidence to the model. The model generates a contextual Markdown advisory rather than returning a preformatted static report. The model has no tool access and cannot execute telecom operations.

A deterministic report remains available as a fallback when the model endpoint is unavailable. The application appends a canonical safety footer to every model response independently of prompt compliance:

> This is a read-only simulation. No network command, routing or configuration change, ticket operation, inventory action, or customer communication has been performed.

## Safe development-step panel

The `POST /chat` contract now returns `development_steps`, `provider`, and `used_fallback` in addition to `response`. Development steps are concise, auditable workflow events—such as selecting synthetic evidence or applying the safety boundary—not private chain-of-thought or hidden model reasoning.

Agent Manager’s built-in **Try It** interface renders the standard `response` field. The agent’s optional `GET /console` view adds a responsive **left-side development-step panel** for demonstrations and renders only those safe milestones.

## Credential handling

The upstream model credential is streamed directly into **OpenBao** and held at a protected generic-secret path. An `ExternalSecret` synchronizes a Kubernetes secret named `telecom-triage-llm-provider` into the data-plane namespace, while the Agent Manager `ReleaseBinding` exposes only a `secretKeyRef` to the runtime. The source repository, application logs, health endpoint, and response payloads do not expose the credential.

`deployment/apply_local_quickstart_llm.sh` accepts `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_PROVIDER_URL` as non-secret configuration inputs and takes the provider credential only on standard input. This supports a provider change without a source-code change. For example, Gemini is configured with:

```bash
printf '%s' "$OPENAI_API_KEY" | ./deployment/apply_local_quickstart_llm.sh
```

For Anthropic, export an approved endpoint/model/provider configuration and pipe the Anthropic credential into the same script. The credential is never written to a command argument, file, repository, or log.

## Verification completed

| Verification | Result |
| --- | --- |
| Initial local FastAPI tests | **6 passed**. |
| Flexible-provider source tests | **9 passed**. |
| Live Gemini call | Returned a dynamic evidence-grounded response with the mandatory safety footer. |
| Agent Manager build | **Succeeded**: `telco-incident-triage-1789569374930`. |
| Runtime secret sync | **Ready** through `ExternalSecret`; only the key name `api_key` was verified. |
| Agent Manager Console Try It | **Succeeded** with a Gemini-synthesized fiber outage advisory for `SIM-SP-2026-0916-017`. |
| Safety boundary | **Present** in the user-visible Console response. |

## Operator usage

Open the deployed agent’s **Try It** page in Agent Manager and submit a telecom incident request. A useful example is:

```text
Compare the two leading root-cause hypotheses for the fiber aggregation loss and recommend the first operator validation.
```

Optionally pass `context.scenario_id` to force one of the synthetic scenarios: `fiber-aggregation-loss`, `mobile-ran-congestion`, or `enterprise-sdwan-latency`. The agent remains advisory and read-only in every case.

For production, replace the local OpenBao wiring with an Agent Manager governed LLM service provider binding. That arrangement injects `LLM_PROVIDER_URL` and `LLM_PROVIDER_KEY` as platform-managed values and supports central policy, usage, rotation, and guardrail management without application redeployment.
