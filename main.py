"""Telecom Network Incident Triage and Resolution Coordinator demo agent.

The Agent Manager Chat Agent implementation selects de-identified mock evidence
deterministically, then uses a configurable OpenAI-compatible LLM to write a
contextual, read-only advisory. It never invokes production telecom systems.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from llm_triage import LLMSettings, TelecomLLMTriage
from mock_data import public_scenarios

APP_VERSION = "0.2.0"
triage = TelecomLLMTriage()

app = FastAPI(
    title="Telecom Network Incident Triage Agent",
    description=(
        "Read-only mock telecom incident correlation service for Agent Manager. "
        "Responses are model-synthesized from de-identified scenario data."
    ),
    version=APP_VERSION,
)


class ChatRequest(BaseModel):
    """Agent Manager's standard Chat Agent request format."""

    message: str = Field(min_length=1, max_length=8000, description="Incident-triage request")
    session_id: str | None = Field(default=None, max_length=256)
    context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Agent Manager's standard Chat Agent response format."""

    response: str


@app.get("/health")
def health() -> dict[str, Any]:
    """Return readiness and non-sensitive model configuration metadata."""
    return {
        "status": "ok",
        "agent": "telecom-incident-triage",
        "version": APP_VERSION,
        "llm": triage.public_status(),
    }


@app.get("/scenarios")
def scenarios() -> dict[str, Any]:
    """List the compact mock scenarios for a demo client."""
    return {"simulation": True, "read_only": True, "scenarios": public_scenarios()}


@app.get("/status")
def status() -> dict[str, Any]:
    """Expose configuration status without exposing credentials or prompts."""
    return {
        "simulation": True,
        "read_only": True,
        "llm": triage.public_status(),
        "providers": ["gemini", "openai", "anthropic", "glm"],
        "history": "bounded in-memory history is retained per session_id",
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Create a grounded, model-synthesized, read-only incident advisory."""
    response = triage.answer(request.message, request.context, request.session_id)
    return ChatResponse(response=response)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
