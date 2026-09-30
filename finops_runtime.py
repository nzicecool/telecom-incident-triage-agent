"""Content-free FinOps runtime client for the governed Agent Manager route.

The helper sends only model name, token counters, a generated request identifier,
and the already-known agent/project labels. It never sends prompts, responses,
credentials, tool arguments, or customer context.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Preflight:
    request_id: str
    allowed: bool
    requires_approval: bool
    reason: str


class FinOpsRuntime:
    def __init__(self, agent_name: str, project_name: str = "default") -> None:
        self.agent_name = os.getenv("FINOPS_AGENT_NAME", agent_name).strip() or agent_name
        self.project_name = os.getenv("FINOPS_PROJECT_NAME", project_name).strip() or project_name
        self.base_url = os.getenv("FINOPS_API_BASE_URL", "").rstrip("/")
        self.token = os.getenv("FINOPS_RUNTIME_TOKEN", "")

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def preflight(self, model: str, expected_input_tokens: int, expected_output_tokens: int) -> Preflight:
        request_id = str(uuid.uuid4())
        if not self.configured:
            return Preflight(request_id, True, False, "FinOps runtime is not configured")
        response = self._post(
            "/finops/runtime/preflight",
            {
                "agentName": self.agent_name,
                "projectName": self.project_name,
                "model": model,
                "expectedInputTokens": max(0, expected_input_tokens),
                "expectedOutputTokens": max(0, expected_output_tokens),
                "requestId": request_id,
            },
        )
        # A configured governance endpoint fails closed. Returning a deterministic
        # advisory is safer than issuing an unmanaged model call after a control
        # plane outage or an invalid runtime credential.
        if not response:
            return Preflight(request_id, False, False, "Governance preflight is unavailable")
        return Preflight(
            request_id,
            bool(response.get("allowed")),
            bool(response.get("requiresApproval")),
            str(response.get("reason") or "Governance preflight denied the model call"),
        )

    def record_usage(self, request_id: str, model: str, input_tokens: int, output_tokens: int) -> None:
        if not self.configured:
            return
        # Metering must not change the customer-facing result once a permitted
        # model response was received. The service deduplicates by request ID.
        self._post(
            "/finops/runtime/usage",
            {
                "agentName": self.agent_name,
                "projectName": self.project_name,
                "model": model,
                "inputTokens": max(0, input_tokens),
                "outputTokens": max(0, output_tokens),
                "requestId": request_id,
            },
        )

    def _post(self, suffix: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{suffix}",
            data=body,
            headers={"Content-Type": "application/json", "X-FinOps-Token": self.token},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=2.5) as response:  # noqa: S310 - configured internal endpoint
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
            return None


def estimate_tokens(messages: list[dict[str, str]]) -> int:
    """Conservative preflight estimate; authoritative counters come from response usage."""
    return max(1, sum(len(str(message.get("content", ""))) for message in messages) // 4)


def openai_usage(completion: Any) -> tuple[int, int]:
    usage = getattr(completion, "usage", None)
    return int(getattr(usage, "prompt_tokens", 0) or 0), int(getattr(usage, "completion_tokens", 0) or 0)


def anthropic_usage(completion: Any) -> tuple[int, int]:
    usage = getattr(completion, "usage", None)
    return int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0)
