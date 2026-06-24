"""FastAPI app: serves the chat UI and exposes the agent, observation trail, and the filled 1040."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from . import agent
from .session import get_or_create

app = FastAPI(title="Agentic Tax Assistant")
STATIC = Path(__file__).resolve().parent.parent / "static"


class ChatIn(BaseModel):
    session_id: Optional[str] = None
    message: str


def _public_state(s) -> dict:
    return {
        "session_id": s.id,
        "facts": s.facts,
        "computation": s.computation,
        "questions_asked": s.questions_asked,
        "question_budget": agent.QUESTION_BUDGET,
        "form_ready": s.pdf is not None,
        "download_url": f"/download/{s.id}" if s.pdf else None,
        "trace": s.trace,
    }


@app.post("/chat")
def chat(body: ChatIn):
    s = get_or_create(body.session_id)
    reply = agent.run_turn(s, body.message)
    return JSONResponse({"reply": reply, **_public_state(s)})


@app.get("/state/{session_id}")
def state(session_id: str):
    return JSONResponse(_public_state(get_or_create(session_id)))


@app.get("/download/{session_id}")
def download(session_id: str):
    s = get_or_create(session_id)
    if not s.pdf:
        return JSONResponse({"error": "form not generated yet"}, status_code=404)
    return Response(
        content=s.pdf, media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="Form_1040_2025.pdf"'},
    )


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
