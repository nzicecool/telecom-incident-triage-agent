#!/usr/bin/env bash
# Securely configure the local Agent Manager Quick Start LLM runtime.
# Reads the provider key exclusively from stdin; never writes or prints it.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QUICK_START_CONTAINER="${QUICK_START_CONTAINER:-amp-quick-start}"
CONTROL_NAMESPACE="default"
DATA_PLANE_NAMESPACE="dp-default-default-default-ccb66d74"
COMPONENT_NAME="telco-incident-triage"
PROVIDER="${LLM_PROVIDER:-gemini}"
MODEL="${LLM_MODEL:-gemini-3-flash-preview}"
PROVIDER_URL="${LLM_PROVIDER_URL:-https://api.manus.im/api/llm-proxy/v1}"

case "$PROVIDER" in
  gemini|anthropic|openai|glm) ;;
  z.ai|zai|z-ai) PROVIDER="glm" ;;
  *)
    echo "Supported LLM_PROVIDER values: gemini, anthropic, openai, glm." >&2
    exit 2
    ;;
esac

if [[ -z "$MODEL" || -z "$PROVIDER_URL" ]]; then
  echo "LLM_MODEL and LLM_PROVIDER_URL must be non-empty." >&2
  exit 2
fi

PATCH_FILE="$(mktemp)"
trap 'rm -f "$PATCH_FILE"' EXIT
jq -n \
  --arg provider "$PROVIDER" \
  --arg model "$MODEL" \
  --arg endpoint "$PROVIDER_URL" \
  '[
    {op:"add", path:"/spec/workloadOverrides/container/env/-", value:{key:"LLM_PROVIDER", value:$provider}},
    {op:"add", path:"/spec/workloadOverrides/container/env/-", value:{key:"LLM_MODEL", value:$model}},
    {op:"add", path:"/spec/workloadOverrides/container/env/-", value:{key:"LLM_PROVIDER_URL", value:$endpoint}},
    {op:"add", path:"/spec/workloadOverrides/container/env/-", value:{key:"LLM_MAX_TOKENS", value:"900"}},
    {op:"add", path:"/spec/workloadOverrides/container/env/-", value:{key:"LLM_HISTORY_MESSAGES", value:"6"}},
    {op:"add", path:"/spec/workloadOverrides/container/env/-", value:{key:"LLM_PROVIDER_KEY", valueFrom:{secretKeyRef:{name:"telecom-triage-llm-provider", key:"api_key"}}}}
  ]' > "$PATCH_FILE"

# The input stream moves directly to OpenBao. The key is never persisted in a
# shell variable, file, command argument, repository, or command output.
cat | docker exec -i "$QUICK_START_CONTAINER" kubectl exec -i -n openbao openbao-0 -- sh -lc '
      set -eu
      export VAULT_ADDR=http://127.0.0.1:8200
      vault kv put secret/default/generic/telecom-triage-llm-provider api_key=- >/dev/null
      vault kv metadata get secret/default/generic/telecom-triage-llm-provider >/dev/null
    '

# Register the control-plane reference and synchronize the runtime Secret into
# the deployed environment. Both manifests reference only a protected OpenBao path.
docker exec -i "$QUICK_START_CONTAINER" kubectl apply -f - < "$ROOT_DIR/deployment/llm-runtime-secret-reference.yaml" >/dev/null
docker exec -i "$QUICK_START_CONTAINER" kubectl apply -f - < "$ROOT_DIR/deployment/llm-data-plane-external-secret.yaml" >/dev/null
docker exec "$QUICK_START_CONTAINER" kubectl wait --for=condition=Ready \
  "externalsecret/telecom-triage-llm-provider" -n "$DATA_PLANE_NAMESPACE" --timeout=90s >/dev/null

# ReleaseBinding owns persistent environment overrides for this environment.
# The JSON patch appends settings without replacing AgentID-generated variables.
docker exec -i "$QUICK_START_CONTAINER" kubectl patch releasebinding \
  "${COMPONENT_NAME}-default" -n "$CONTROL_NAMESPACE" --type=json \
  --patch-file=/dev/stdin < "$PATCH_FILE" >/dev/null

docker exec "$QUICK_START_CONTAINER" sh -lc "
  set -eu
  kubectl get releasebinding '${COMPONENT_NAME}-default' -n '${CONTROL_NAMESPACE}' -o json \
    | jq -e '.spec.workloadOverrides.container.env | map(.key) | index(\"LLM_PROVIDER_KEY\") != null' >/dev/null
  kubectl get externalsecret telecom-triage-llm-provider -n '${DATA_PLANE_NAMESPACE}' -o json \
    | jq -e '.status.conditions[] | select(.type == \"Ready\" and .status == \"True\")' >/dev/null
"

echo "Secure ${PROVIDER} LLM runtime configuration applied."
