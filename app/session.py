"""In-memory session state. One process, free-tier hosting — a dict is enough."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Session:
    id: str
    messages: list = field(default_factory=list)   # Anthropic message history (the chat loop's state)
    facts: dict = field(default_factory=dict)        # recorded W-2 / filing-status data
    computation: dict | None = None                  # last compute_1040 result
    pdf: bytes | None = None                         # filled 1040, ready to download
    trace: list = field(default_factory=list)        # observation log (every decision & action)
    questions_asked: int = 0                         # guardrail counter

    def observe(self, kind: str, detail: dict) -> None:
        self.trace.append({"t": round(time.time(), 3), "kind": kind, **detail})


_SESSIONS: dict[str, Session] = {}


def get_or_create(session_id: str | None) -> Session:
    if session_id and session_id in _SESSIONS:
        return _SESSIONS[session_id]
    s = Session(id=uuid.uuid4().hex)
    _SESSIONS[s.id] = s
    return s
