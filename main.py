"""Telecom Network Incident Triage and Resolution Coordinator demo agent.

This service implements the WSO2 Agent Manager Chat Agent contract. It deliberately
uses deterministic mock data and never performs production-network actions.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from incident_engine import answer
from mock_data import public_scenarios

APP_VERSION = "0.1.0"

app = FastAPI(
    title="Telecom Network Incident Triage Agent",
    description="Read-only mock telecom incident correlation service for Agent Manager.",
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
def health() -> dict[str, str]:
    """Return a non-sensitive readiness response."""
    return {"status": "ok", "agent": "telecom-incident-triage", "version": APP_VERSION}


@app.get("/scenarios")
def scenarios() -> dict[str, Any]:
    """List the compact mock scenarios for a demo client."""
    return {"simulation": True, "read_only": True, "scenarios": public_scenarios()}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Create a grounded, read-only incident triage briefing."""
    return ChatResponse(response=answer(request.message, request.context))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
