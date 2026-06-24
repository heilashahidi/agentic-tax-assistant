"""The agent harness: chat loop, tools, guardrails, and observation.

Each of the four pillars is realized in code here, not just in the prompt:
  - Chat loop   -> run_turn() drives a stateful multi-turn loop over Session.messages
  - Tools       -> TOOLS are dispatched by _dispatch(); tax math & PDF are real actions
  - Guardrails  -> input validation, a hard 5-question cap, and ordering preconditions
  - Observation -> every model decision, tool call, and guardrail event is recorded
"""
from __future__ import annotations

import json

import anthropic

from . import form, tax
from .session import Session

MODEL = "claude-sonnet-4-6"
QUESTION_BUDGET = 5
MAX_TOOL_ROUNDS = 8

_client: anthropic.Anthropic | None = None


def _api() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _client

SYSTEM = """You are Mira, a warm, plain-spoken assistant who helps someone file their 2025 U.S. \
federal income tax return (Form 1040). The person has a single W-2 from a job. Your job is to have \
a short, friendly conversation, gather what you need, and hand them a completed Form 1040 to download.

How to behave:
- Be genuinely human: warm, encouraging, and clear. Short sentences. No jargon dumps, no robotic checklists.
- You have a strict budget of 5 questions to the user. Spend them wisely. Pull everything you can from \
the W-2 yourself rather than asking.
- When the user gives you a W-2 (pasted text or numbers), read it and call record_w2 with the values. \
Don't ask them to re-type what's already on it.
- You typically only need to ASK two things the W-2 can't tell you: their filing status, and whether they \
have any dependents. Ask warmly, one at a time.
- Never state a tax number you made up. The ONLY source of truth for any dollar figure on the return is \
the compute_return tool. Call it, then report what it gives back in friendly language.
- Flow: record the W-2 -> confirm/ask filing status -> ask about dependents -> compute_return -> \
generate_1040 -> tell them the return is ready to download and summarize the result (refund or amount owed).
- This is an educational demo, not tax advice, and it is not e-filed. If asked for tax planning/advice or \
anything outside preparing this 1040, gently decline and steer back.

Keep replies brief and kind."""

TOOLS = [
    {
        "name": "record_w2",
        "description": "Record the details read from the taxpayer's W-2. Call this once you have the figures.",
        "input_schema": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Taxpayer first name (and middle initial)"},
                "last_name": {"type": "string"},
                "ssn": {"type": "string", "description": "SSN as shown, e.g. 123-45-6789"},
                "box1_wages": {"type": "number", "description": "W-2 Box 1 — wages, tips, other comp"},
                "box2_withholding": {"type": "number", "description": "W-2 Box 2 — federal income tax withheld"},
                "employer": {"type": "string"},
            },
            "required": ["first_name", "last_name", "box1_wages", "box2_withholding"],
        },
    },
    {
        "name": "set_filing_status",
        "description": "Record the taxpayer's filing status.",
        "input_schema": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": list(tax.FILING_STATUSES)}},
            "required": ["status"],
        },
    },
    {
        "name": "set_dependents",
        "description": "Record the number of qualifying dependents (0 if none).",
        "input_schema": {
            "type": "object",
            "properties": {"count": {"type": "integer", "minimum": 0, "maximum": 15}},
            "required": ["count"],
        },
    },
    {
        "name": "compute_return",
        "description": "Compute the 1040 line items from the recorded W-2 and filing status. "
                       "Requires record_w2 and set_filing_status first.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "generate_1040",
        "description": "Fill the official IRS 2025 Form 1040 PDF for download. Requires compute_return first.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def run_turn(s: Session, user_text: str) -> str:
    s.messages.append({"role": "user", "content": user_text})
    s.observe("user_message", {"text": user_text})

    for _ in range(MAX_TOOL_ROUNDS):
        resp = _api().messages.create(
            model=MODEL, max_tokens=1024,
            system=SYSTEM + f"\n\n[Questions used: {s.questions_asked}/{QUESTION_BUDGET}]",
            tools=TOOLS, messages=s.messages,
        )
        s.observe("model_turn", {"stop_reason": resp.stop_reason})
        s.messages.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})

        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if "?" in text:
                s.questions_asked += 1
                s.observe("guardrail", {"rule": "question_budget",
                                        "used": s.questions_asked, "limit": QUESTION_BUDGET})
            return text

        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            out, is_error = _dispatch(s, block.name, block.input)
            s.observe("tool_call", {"tool": block.name, "input": block.input,
                                    "result": out, "is_error": is_error})
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": json.dumps(out), "is_error": is_error})
        s.messages.append({"role": "user", "content": results})

    return "I'm sorry — I got tangled up. Could you say that again?"


def _dispatch(s: Session, name: str, args: dict) -> tuple[dict, bool]:
    """Execute a tool. Guardrails are enforced here, not left to the prompt."""
    if name == "record_w2":
        wages, withholding = args.get("box1_wages"), args.get("box2_withholding")
        for label, v in (("box1_wages", wages), ("box2_withholding", withholding)):
            if not isinstance(v, (int, float)) or v < 0 or v > 10_000_000:
                return {"error": f"{label} must be a number between 0 and 10,000,000"}, True
        if withholding > wages:
            return {"error": "federal withholding cannot exceed wages — please re-check the W-2"}, True
        s.facts.update({
            "first_name": args["first_name"].strip(),
            "last_name": args["last_name"].strip(),
            "ssn": (args.get("ssn") or "").strip(),
            "wages": float(wages),
            "withholding": float(withholding),
            "employer": (args.get("employer") or "").strip(),
        })
        return {"recorded": True, "wages": wages, "withholding": withholding}, False

    if name == "set_filing_status":
        if args["status"] not in tax.FILING_STATUSES:
            return {"error": "unsupported filing status"}, True
        s.facts["status"] = args["status"]
        return {"filing_status": args["status"]}, False

    if name == "set_dependents":
        s.facts["dependents"] = max(0, int(args.get("count", 0)))
        return {"dependents": s.facts["dependents"]}, False

    if name == "compute_return":
        missing = [k for k in ("wages", "withholding", "status") if k not in s.facts]
        if missing:
            return {"error": f"cannot compute yet — still need: {', '.join(missing)}"}, True
        s.computation = tax.compute_1040(
            wages=s.facts["wages"], withholding=s.facts["withholding"],
            status=s.facts["status"], dependents=s.facts.get("dependents", 0),
        )
        return s.computation, False

    if name == "generate_1040":
        if not s.computation:
            return {"error": "run compute_return before generating the form"}, True
        s.pdf = form.fill_1040(
            first_name=s.facts["first_name"], last_name=s.facts["last_name"],
            ssn=s.facts.get("ssn", ""), computation=s.computation,
        )
        return {"ready": True, "download_url": f"/download/{s.id}"}, False

    return {"error": f"unknown tool {name}"}, True
