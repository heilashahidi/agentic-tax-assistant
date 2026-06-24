# DECISIONS

Key choices for the open items, and why.

**Language / framework.** Python + FastAPI. Smallest path from input to outcome, deploys to Render
in one file, and the tax math + PDF work live naturally in Python (`pypdf`).

**Model / provider.** Anthropic Claude (`claude-sonnet-4-6`). Chosen for the best speed/quality balance:
fast enough for snappy live turns while keeping the warm dialogue and reliable tool use the brief
judges on. No extended thinking — turns stay snappy for a live judge.

**The four pillars — enforced in code, not just prompted (`app/agent.py`).**
- *Chat loop:* `run_turn()` drives a stateful loop over `Session.messages`; state (history, recorded
  facts, computation) persists across turns server-side.
- *Tools:* five real tools (`record_w2`, `set_filing_status`, `set_dependents`, `compute_return`,
  `generate_1040`). The tax math and the filled PDF are produced by tools, never by the model.
- *Guardrails:* code-level, so they're real rather than cosmetic — numeric W-2 validation
  (range + withholding ≤ wages), a hard 5-question counter, and ordering preconditions
  (`compute_return` refuses without wages+status; `generate_1040` refuses without a computation).
  The model is also forbidden from inventing dollar figures — the only source of truth is the tool.
- *Observation:* every user message, model decision, tool call (inputs + outputs), and guardrail event
  is appended to `Session.trace`, returned with each `/chat` response, and rendered live in the UI's
  "Agent activity" panel — plus available at `/state/{id}`.

**How the 1040 is obtained & filled.** The official IRS **2025** `f1040.pdf` (a real AcroForm). Field
names were mapped from widget coordinates to line numbers (`app/form.py`); `pypdf` writes the values.
The output is the genuine government form, not a look-alike.

**Where the W-2 comes from.** The user pastes W-2 text into the chat (a "Paste a sample W-2" button
supplies a realistic fake one). The agent *reads* it — extracting Box 1 / Box 2 / name / SSN via the
`record_w2` tool — rather than making the user re-type fields.

**Tax computation.** Deterministic Python (`app/tax.py`) for tax year 2025: OBBBA standard deductions
(printed on the IRS form: $15,750 / $31,500 / $23,625), the 2025 bracket schedule, and the IRS
**Tax Table** method (round to the $50 bracket, use its midpoint, round half up) for taxable income
under $100k. Covers all four filing statuses and a simple Child Tax Credit ($2,200/dependent,
nonrefundable) so a dependent is handled gracefully. Single-W-2 scope: no Schedules, itemizing, or
other income.

**Conversation design (≤5 questions).** The W-2 yields wages, withholding, name, and SSN, so the agent
typically asks only two questions — filing status and dependents — leaving headroom under the budget.

**State & sessions.** In-memory dict keyed by a session id minted on first message. One free-tier
instance, so a dict is the right amount of machinery; nothing to persist between deploys.

**Hosting.** Render (free web service), config in `render.yaml`. Set `ANTHROPIC_API_KEY` in the
dashboard.

**Testing.** `tests/test_tax.py` pins the math (refund, owing, zero-tax, MFJ, dependents). The PDF fill
is verified by reading values back out of the generated AcroForm.

**Scope guards.** Educational demo, no real PII, no e-filing — stated in the UI and the system prompt;
the agent declines tax-advice / out-of-scope requests.
