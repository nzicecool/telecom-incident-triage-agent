"""Model-backed, mock-data-grounded telecom incident triage.

The adapter intentionally separates three concerns:

* Scenario selection and evidence are deterministic and come only from mock_data.
* Natural-language synthesis is delegated to a configurable LLM provider.
* Failure to reach the LLM degrades safely to the deterministic advisory.

Supported providers are Gemini, OpenAI, Z.ai/GLM, and Anthropic. Gemini, OpenAI,
and GLM use OpenAI-compatible Chat Completions endpoints; Anthropic uses its
native Messages API. No tool calls are exposed to any model. The service is
read-only and the model is never instructed to execute network operations,
create tickets, or contact customers.
"""

from __future__ import annotations

import json
import os
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from anthropic import (
    APIConnectionError as AnthropicAPIConnectionError,
    APIError as AnthropicAPIError,
    Anthropic,
    AuthenticationError as AnthropicAuthenticationError,
    RateLimitError as AnthropicRateLimitError,
)
from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError

from incident_engine import (
    ScenarioNotFound,
    build_triage_report,
    list_scenarios_report,
    select_scenario,
)

DEFAULT_MODEL = "gemini-3-flash-preview"
DEFAULT_BASE_URL = "https://api.manus.im/api/llm-proxy/v1"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_HISTORY_MESSAGES = 6
MAX_HISTORY_MESSAGES = 12
OPENAI_COMPATIBLE_PROVIDERS = {"gemini", "openai", "glm", "zai", "z.ai"}
SUPPORTED_PROVIDERS = ("gemini", "anthropic", "openai", "glm")

SYSTEM_PROMPT = """You are a telecom network incident triage analyst in a read-only simulation.

Use ONLY the supplied mock evidence. Do not invent alarms, customer impacts,
change records, root causes, dates, identifiers, or remediation outcomes.
Clearly separate evidence from hypotheses. Give practical, operator-controlled
next steps, and preserve approval gates.

Never claim to execute network commands, reroute traffic, change configuration,
create or close tickets, reserve inventory, send notifications, or contact
customers. If asked to perform an action, explain that you can only prepare an
advisory or draft for authorized human review.

Answer in concise Markdown with these sections when relevant:
1. Assessment
2. Evidence and impact
3. Hypotheses
4. Recommended operator-controlled next steps
5. Approval gates
6. Safety boundary

The scenario is synthetic, de-identified, and suitable only for demonstration.
"""

SAFETY_FOOTER = (
    "\n\n## Safety boundary\n"
    "This is a read-only simulation. No network command, routing or configuration "
    "change, ticket operation, inventory action, or customer communication has been performed."
)


@dataclass(frozen=True)
class LLMSettings:
    """Runtime-configurable LLM connection settings.

    Agent Manager can inject `LLM_PROVIDER_URL` and `LLM_PROVIDER_KEY` through a
    governed provider binding. This local Quick Start injects equivalent values
    from a Kubernetes secret. Credentials are read only from runtime environment
    variables and never returned by APIs or logged.
    """

    provider: str
    model: str
    base_url: str
    api_key: str | None
    max_tokens: int
    history_messages: int

    @classmethod
    def from_environment(cls) -> "LLMSettings":
        provider = _normalize_provider(os.getenv("LLM_PROVIDER", "gemini"))
        model = os.getenv("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        if provider == "anthropic":
            base_url = (os.getenv("LLM_PROVIDER_URL") or DEFAULT_ANTHROPIC_BASE_URL).rstrip("/")
            api_key = os.getenv("LLM_PROVIDER_KEY") or os.getenv("ANTHROPIC_API_KEY")
        else:
            base_url = (
                os.getenv("LLM_PROVIDER_URL")
                or os.getenv("OPENAI_API_BASE")
                or DEFAULT_BASE_URL
            ).rstrip("/")
            api_key = os.getenv("LLM_PROVIDER_KEY") or os.getenv("OPENAI_API_KEY")
        max_tokens = _bounded_int(os.getenv("LLM_MAX_TOKENS"), 900, 128, 2048)
        history_messages = _bounded_int(
            os.getenv("LLM_HISTORY_MESSAGES"),
            DEFAULT_HISTORY_MESSAGES,
            0,
            MAX_HISTORY_MESSAGES,
        )
        return cls(provider, model, base_url, api_key, max_tokens, history_messages)

    @property
    def protocol(self) -> str:
        return "anthropic-messages" if self.provider == "anthropic" else "openai-chat-completions"

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model and self.provider in SUPPORTED_PROVIDERS)

    def public_status(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "provider": self.provider,
            "model": self.model,
            "protocol": self.protocol,
            "history_messages": self.history_messages,
            "supported_providers": list(SUPPORTED_PROVIDERS),
            "fallback": "deterministic mock-data advisory",
        }


@dataclass(frozen=True)
class TriageResult:
    """A response plus safe, auditable workflow milestones for a custom UI."""

    response: str
    development_steps: list[str]
    provider: str | None
    used_fallback: bool


def _normalize_provider(value: str | None) -> str:
    provider = (value or "gemini").strip().lower()
    aliases = {"z.ai": "glm", "zai": "glm", "z-ai": "glm"}
    return aliases.get(provider, provider or "gemini")


def _bounded_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value or default)
    except ValueError:
        return default
    return min(maximum, max(minimum, parsed))


class SessionHistory:
    """A bounded in-process prompt history keyed by Agent Manager session ID."""

    def __init__(self, max_messages: int) -> None:
        self._max_messages = max_messages
        self._items: dict[str, deque[dict[str, str]]] = defaultdict(
            lambda: deque(maxlen=max_messages or 1)
        )
        self._lock = threading.Lock()

    def messages(self, session_id: str | None) -> list[dict[str, str]]:
        if not session_id or not self._max_messages:
            return []
        with self._lock:
            return list(self._items[session_id])

    def add_turn(self, session_id: str | None, user: str, assistant: str) -> None:
        if not session_id or not self._max_messages:
            return
        with self._lock:
            self._items[session_id].append({"role": "user", "content": user})
            self._items[session_id].append({"role": "assistant", "content": assistant})


class ModelUnavailable(RuntimeError):
    """Raised when a configured model cannot serve a request."""


class TelecomLLMTriage:
    """Generates a grounded answer while preserving deterministic data selection."""

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or LLMSettings.from_environment()
        self.history = SessionHistory(self.settings.history_messages)
        self._openai_client: OpenAI | None = None
        self._anthropic_client: Anthropic | None = None

    def public_status(self) -> dict[str, Any]:
        return self.settings.public_status()

    def answer(self, message: str, context: dict[str, Any] | None, session_id: str | None) -> str:
        """Preserve the simple string-returning integration used by legacy callers."""
        return self.answer_with_metadata(message, context, session_id).response

    def answer_with_metadata(
        self,
        message: str,
        context: dict[str, Any] | None,
        session_id: str | None,
    ) -> TriageResult:
        context = context or {}
        normalized = message.lower().replace("_", "-").strip()
        if any(term in normalized for term in ("help", "list", "scenario", "mock data", "available")):
            response = list_scenarios_report()
            self.history.add_turn(session_id, message, response)
            return TriageResult(
                response=response,
                development_steps=[
                    "Recognized a scenario-discovery request.",
                    "Presented the available synthetic, read-only scenarios.",
                ],
                provider=None,
                used_fallback=False,
            )

        try:
            scenario = select_scenario(message, context)
        except ScenarioNotFound as exc:
            response = f"{exc}\n\n{list_scenarios_report()}"
            self.history.add_turn(session_id, message, response)
            return TriageResult(
                response=response,
                development_steps=[
                    "Validated the requested scenario identifier.",
                    "Returned the synthetic scenario catalogue without model invocation.",
                ],
                provider=None,
                used_fallback=False,
            )

        steps = [
            "Selected the applicable synthetic incident from the request context.",
            "Retrieved only the selected mock telemetry, topology, change context, and runbook evidence.",
            "Applied read-only and approval-gate constraints before response synthesis.",
        ]
        fallback = build_triage_report(scenario)
        if not self.settings.configured:
            steps.append("Model provider is not configured; returned the deterministic advisory fallback.")
            self.history.add_turn(session_id, message, fallback)
            return TriageResult(fallback, steps, None, True)

        try:
            response = self._generate(message, scenario, session_id)
            steps.append(f"Synthesized an evidence-grounded advisory through the configured {self.settings.provider} provider.")
            used_fallback = False
        except ModelUnavailable:
            response = fallback
            steps.append("The model invocation was unavailable; returned the deterministic advisory fallback.")
            used_fallback = True
        self.history.add_turn(session_id, message, response)
        return TriageResult(response, steps, self.settings.provider if not used_fallback else None, used_fallback)

    def _generate(self, message: str, scenario: dict[str, Any], session_id: str | None) -> str:
        evidence = json.dumps(scenario, ensure_ascii=False, indent=2)
        user_message = (
            f"User request:\n{message}\n\n"
            f"Selected mock incident evidence (authoritative):\n```json\n{evidence}\n```\n\n"
            "Create a grounded advisory response. The safety boundary must be explicit."
        )
        if self.settings.provider == "anthropic":
            response = self._generate_anthropic(user_message, session_id)
        else:
            response = self._generate_openai_compatible(user_message, session_id)
        # Application code appends a canonical boundary. Operational safeguards
        # never depend on a model's probabilistic adherence or exact wording.
        return response + SAFETY_FOOTER

    def _generate_openai_compatible(self, user_message: str, session_id: str | None) -> str:
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history.messages(session_id))
        messages.append({"role": "user", "content": user_message})
        try:
            completion = self._get_openai_client().chat.completions.create(
                model=self.settings.model,
                messages=messages,
                max_tokens=self.settings.max_tokens,
            )
        except (APIConnectionError, AuthenticationError, RateLimitError, APIError) as exc:
            raise ModelUnavailable("Model request unavailable") from exc
        except Exception as exc:  # Defensive boundary for provider-specific SDK errors.
            raise ModelUnavailable("Model request failed") from exc

        text = completion.choices[0].message.content if completion.choices else None
        return _require_text(text)

    def _generate_anthropic(self, user_message: str, session_id: str | None) -> str:
        messages = self.history.messages(session_id)
        messages.append({"role": "user", "content": user_message})
        try:
            completion = self._get_anthropic_client().messages.create(
                model=self.settings.model,
                max_tokens=self.settings.max_tokens,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
        except (
            AnthropicAPIConnectionError,
            AnthropicAuthenticationError,
            AnthropicRateLimitError,
            AnthropicAPIError,
        ) as exc:
            raise ModelUnavailable("Model request unavailable") from exc
        except Exception as exc:  # Defensive boundary for provider-specific SDK errors.
            raise ModelUnavailable("Model request failed") from exc

        text = "".join(
            block.text for block in completion.content if getattr(block, "type", "") == "text"
        )
        return _require_text(text)

    def _get_openai_client(self) -> OpenAI:
        if self._openai_client is None:
            self._openai_client = OpenAI(api_key=self.settings.api_key, base_url=self.settings.base_url)
        return self._openai_client

    def _get_anthropic_client(self) -> Anthropic:
        if self._anthropic_client is None:
            self._anthropic_client = Anthropic(api_key=self.settings.api_key, base_url=self.settings.base_url)
        return self._anthropic_client


def _require_text(text: str | None) -> str:
    if not text or not text.strip():
        raise ModelUnavailable("Model returned no visible response")
    return text.strip()
