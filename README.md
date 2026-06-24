# Agentic Tax Assistant

A warm, conversational agent that helps someone file a 2025 U.S. federal **Form 1040** from a single
W-2, and hands back the completed, downloadable IRS PDF — built on a harness that demonstrates the four
pillars (chat loop, tools, guardrails, observation). See [`DECISIONS.md`](DECISIONS.md) for the design.

## Live

Deployed on Render: **https://agentic-tax-assistant.onrender.com/**

> Free tier: the service sleeps after ~15 min idle and takes ~50s to wake on the first request.

## Run locally (one command)

```bash
export ANTHROPIC_API_KEY=sk-...
./run.sh          # serves on http://localhost:8000
```

Open the URL, click **Paste a sample W-2**, and chat. The right-hand panel shows the agent's live
activity (tool calls, guardrails, decisions); a download button appears when the 1040 is ready.

## Test

```bash
pip install pytest && python3 -m pytest tests/ -q
```

## Deploy to Render

Push to GitHub, create a Render **Web Service** from the repo (it reads `render.yaml`), and set the
`ANTHROPIC_API_KEY` environment variable in the dashboard.
