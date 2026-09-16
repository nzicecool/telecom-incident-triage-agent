#!/usr/bin/env bash
# Securely configure the local Agent Manager Quick Start LLM runtime.
# Reads the provider key exclusively from stdin; never writes or prints it.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QUICK_START_CONTAINER="${QUICK_START_CONTAINER:-amp-quick-start}"
CONTROL_NAMESPACE="default"
DATA_PLANE_NAMESPACE="dp-default-default-default-ccb66d74"
COMPONENT_NAME="telco-incident-triage"

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
  --patch-file=/dev/stdin < "$ROOT_DIR/deployment/release-binding-llm-env-patch.json" >/dev/null

docker exec "$QUICK_START_CONTAINER" sh -lc "
  set -eu
  kubectl get releasebinding '${COMPONENT_NAME}-default' -n '${CONTROL_NAMESPACE}' -o json \
    | jq -e '.spec.workloadOverrides.container.env | map(.key) | index(\"LLM_PROVIDER_KEY\") != null' >/dev/null
  kubectl get externalsecret telecom-triage-llm-provider -n '${DATA_PLANE_NAMESPACE}' -o json \
    | jq -e '.status.conditions[] | select(.type == \"Ready\" and .status == \"True\")' >/dev/null
"

echo "Secure LLM runtime configuration applied."
