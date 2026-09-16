"""Telecom Network Incident Triage and Resolution Coordinator demo agent.

The Agent Manager Chat Agent implementation selects de-identified mock evidence
deterministically, then uses a configurable LLM to write a contextual, read-only
advisory. It never invokes production telecom systems.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from llm_triage import TelecomLLMTriage
from mock_data import public_scenarios

APP_VERSION = "0.3.0"
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
    """Chat answer with safe, user-visible processing milestones.

    `development_steps` contains an auditable workflow summary, not hidden
    chain-of-thought or model reasoning. Agent Manager's standard Console uses
    `response`; the optional `/console` view displays the milestones in a left
    panel for standalone demonstrations.
    """

    response: str
    development_steps: list[str]
    provider: str | None = None
    used_fallback: bool = False


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
        "providers": ["gemini", "anthropic", "openai", "glm"],
        "history": "bounded in-memory history is retained per session_id",
        "console": "GET /console displays safe workflow milestones in a left panel",
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Create a grounded, model-synthesized, read-only incident advisory."""
    result = triage.answer_with_metadata(request.message, request.context, request.session_id)
    return ChatResponse(
        response=result.response,
        development_steps=result.development_steps,
        provider=result.provider,
        used_fallback=result.used_fallback,
    )


@app.get("/console", response_class=HTMLResponse, include_in_schema=False)
def custom_console() -> str:
    """Provide a standalone demo console with a safe workflow panel.

    The default Agent Manager Console renders only the standard `response`
    field. This optional page makes the supplementary safe milestones visible
    without revealing private model reasoning.
    """
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Telecom Incident Triage</title><style>
:root { color-scheme: dark; --bg:#0c1422; --panel:#131f32; --line:#2d405d; --text:#edf4ff; --muted:#a9b8ce; --accent:#7ed0ff; --warn:#ffd38a; }
* { box-sizing:border-box; } body { margin:0; min-height:100vh; background:var(--bg); color:var(--text); font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif; }
.app { display:grid; grid-template-columns:300px minmax(0,1fr); min-height:100vh; }
aside { padding:30px 24px; border-right:1px solid var(--line); background:#101b2c; } main { padding:34px; max-width:1000px; width:100%; margin:auto; }
h1 { font-size:24px; margin:0 0 6px; } h2 { font-size:14px; text-transform:uppercase; letter-spacing:.08em; color:var(--accent); margin:28px 0 12px; }
p { color:var(--muted); margin:0 0 14px; } ol { padding-left:22px; color:var(--muted); } li { margin:10px 0; } .badge { display:inline-block; font-size:12px; padding:3px 9px; border:1px solid var(--line); border-radius:999px; color:var(--accent); }
textarea { width:100%; min-height:110px; padding:14px; border:1px solid var(--line); border-radius:10px; color:var(--text); background:#0b1728; resize:vertical; font:inherit; } button { margin-top:12px; padding:10px 16px; border:0; border-radius:8px; background:var(--accent); color:#052032; font-weight:700; cursor:pointer; } button:disabled { opacity:.55; cursor:wait; }
#answer { white-space:pre-wrap; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:20px; min-height:80px; margin-top:22px; } .notice { color:var(--warn); font-size:13px; } @media(max-width:760px){.app{grid-template-columns:1fr}aside{border-right:0;border-bottom:1px solid var(--line)}}
</style></head><body><div class="app"><aside><span class="badge">Read-only simulation</span><h2>Development steps</h2><ol id="steps"><li>Awaiting a triage request.</li></ol><p class="notice">These are auditable workflow milestones, not private model reasoning.</p></aside><main><h1>Telecom Incident Triage</h1><p>Submit a mock incident request. The agent returns an evidence-grounded advisory and never executes network actions.</p><textarea id="message">Compare the two leading root-cause hypotheses for the fiber aggregation loss and recommend the first operator validation.</textarea><br><button id="send">Generate advisory</button><div id="answer">Ready for a mock incident request.</div></main></div><script>
const send=document.getElementById('send'), input=document.getElementById('message'), answer=document.getElementById('answer'), steps=document.getElementById('steps');
function renderSteps(items){ steps.replaceChildren(); for(const item of items){ const li=document.createElement('li'); li.textContent=item; steps.appendChild(li); } }
send.addEventListener('click', async()=>{ send.disabled=true; answer.textContent='Generating an evidence-grounded advisory…'; renderSteps(['Selecting a synthetic incident and preparing approved evidence.']); try { const r=await fetch('./chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:input.value,session_id:'standalone-console',context:{scenario_id:'fiber-aggregation-loss'}})}); const payload=await r.json(); if(!r.ok) throw new Error(payload.detail||'Request failed'); answer.textContent=payload.response; renderSteps(payload.development_steps||[]); } catch(error) { answer.textContent=`Unable to obtain an advisory: ${error.message}`; renderSteps(['The request could not complete. No telecom operation was executed.']); } finally { send.disabled=false; } });
</script></body></html>"""


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
