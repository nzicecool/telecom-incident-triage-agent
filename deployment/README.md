# LLM Runtime Configuration

These manifests are safe to commit because they contain **references only**, not an API key. The model credential must be created in OpenBao at `secret/default/generic/telecom-triage-llm-provider`, property `api_key`. OpenChoreo synchronizes it into the deployed data-plane namespace through an `ExternalSecret`.

`component-llm-environment-variables.json` configures the existing `telco-incident-triage` component with a Gemini default through `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_PROVIDER_URL`. The adapter is OpenAI-compatible: set these values to another approved Gemini, Anthropic, OpenAI, or GLM-compatible gateway without changing source code.

The credential reference must remain `LLM_PROVIDER_KEY`. The FastAPI service never logs or returns the credential; its `/health` and `/status` routes expose only model and provider metadata.

For the local Quick Start, run `printf '%s' "$OPENAI_API_KEY" | ./deployment/apply_local_quickstart_llm.sh` from the repository root after making the script executable. It reads the credential only from standard input, stores it in OpenBao, creates an ExternalSecret in the data plane, and appends persistent `ReleaseBinding` overrides without replacing AgentID variables. No secret is written into the repository or a shell command argument.
