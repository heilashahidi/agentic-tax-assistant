#!/usr/bin/env bash
# One-command local run. Requires an Anthropic API key.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
: "${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY first (export ANTHROPIC_API_KEY=sk-...)}"
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
