"""Model-backed, mock-data-grounded telecom incident triage.

The adapter intentionally separates three concerns:

* Scenario selection and evidence are deterministic and come only from mock_data.
* Natural-language synthesis is delegated to a configured OpenAI-compatible LLM.
* Failure to reach the LLM degrades safely to the existing deterministic advisory.

No tool calls are exposed to the model. The service remains read-only and the
model is never instructed to execute network operations, create tickets, or
contact customers.
"""

from __future__ import annotations

import json
import os
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError

from incident_engine import (
    ScenarioNotFound,
    build_triage_report,
    list_scenarios_report,
    select_scenario,
)

DEFAULT_MODEL = "gemini-3-flash-preview"
DEFAULT_BASE_URL = "https://api.manus.im/api/llm-proxy/v1"
DEFAULT_HISTORY_MESSAGES = 6
MAX_HISTORY_MESSAGES = 12

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

    An Agent Manager LLM provider binding can inject LLM_PROVIDER_URL and
    LLM_PROVIDER_KEY. For this local Quick Start deployment, OPENAI_API_BASE and
    OPENAI_API_KEY provide an OpenAI-compatible fallback. The key is always read
    from the runtime environment and is never returned by the API or logged.
    """

    provider: str
    model: str
    base_url: str
    api_key: str | None
    max_tokens: int
    history_messages: int

    @classmethod
    def from_environment(cls) -> "LLMSettings":
        provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower() or "gemini"
        model = os.getenv("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
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
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def public_status(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "provider": self.provider,
            "model": self.model,
            "history_messages": self.history_messages,
            "fallback": "deterministic mock-data advisory",
        }


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
        self._client: OpenAI | None = None

    def public_status(self) -> dict[str, Any]:
        return self.settings.public_status()

    def answer(self, message: str, context: dict[str, Any] | None, session_id: str | None) -> str:
        context = context or {}
        normalized = message.lower().replace("_", "-").strip()
        if any(term in normalized for term in ("help", "list", "scenario", "mock data", "available")):
            response = list_scenarios_report()
            self.history.add_turn(session_id, message, response)
            return response

        try:
            scenario = select_scenario(message, context)
        except ScenarioNotFound as exc:
            response = f"{exc}\n\n{list_scenarios_report()}"
            self.history.add_turn(session_id, message, response)
            return response

        fallback = build_triage_report(scenario)
        if not self.settings.configured:
            self.history.add_turn(session_id, message, fallback)
            return fallback

        try:
            response = self._generate(message, scenario, session_id)
        except ModelUnavailable:
            response = fallback
        self.history.add_turn(session_id, message, response)
        return response

    def _generate(self, message: str, scenario: dict[str, Any], session_id: str | None) -> str:
        client = self._get_client()
        evidence = json.dumps(scenario, ensure_ascii=False, indent=2)
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history.messages(session_id))
        messages.append(
            {
                "role": "user",
                "content": (
                    f"User request:\n{message}\n\n"
                    f"Selected mock incident evidence (authoritative):\n```json\n{evidence}\n```\n\n"
                    "Create a grounded advisory response. The safety boundary must be explicit."
                ),
            }
        )
        try:
            completion = client.chat.completions.create(
                model=self.settings.model,
                messages=messages,
                max_tokens=self.settings.max_tokens,
            )
        except (APIConnectionError, AuthenticationError, RateLimitError, APIError) as exc:
            raise ModelUnavailable("Model request unavailable") from exc
        except Exception as exc:  # Defensive boundary for provider-specific SDK errors.
            raise ModelUnavailable("Model request failed") from exc

        text = completion.choices[0].message.content if completion.choices else None
        if not text or not text.strip():
            raise ModelUnavailable("Model returned no visible response")
        response = text.strip()
        # The model is instructed to include a boundary, but the application
        # appends a canonical one independently so operational safeguards never
        # depend on probabilistic output adherence or exact model wording.
        return response + SAFETY_FOOTER

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self.settings.api_key, base_url=self.settings.base_url)
        return self._client
