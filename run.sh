#!/usr/bin/env bash
# ============================================================
#  AI Customer Support Assistant — one-command production run
#  Builds the frontend and serves everything from FastAPI on
#  http://0.0.0.0:8000 (reachable over the LAN).
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

PORT="${BACKEND_PORT:-8000}"
PY=".venv/bin/python"

# ---- Preconditions ----
if [ ! -d ".venv" ]; then
  echo "==> Creating virtualenv & installing backend deps..."
  python3.12 -m venv .venv
  .venv/bin/pip install --upgrade pip >/dev/null
  .venv/bin/pip install -r backend/requirements.txt
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "==> Created .env from template."
fi

# ---- Ensure models are present ----
echo "==> Checking Ollama models..."
ollama list | grep -q "gemma3" || ollama pull gemma3:4b
ollama list | grep -q "nomic-embed-text" || ollama pull nomic-embed-text

# ---- Build frontend ----
if [ ! -d "frontend/node_modules" ]; then
  echo "==> Installing frontend deps..."
  (cd frontend && npm install)
fi
echo "==> Building frontend..."
(cd frontend && npm run build)

# ---- LAN address ----
IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 127.0.0.1)"
echo ""
echo "============================================================"
echo "  AI Customer Support Assistant is starting (offline)"
echo "  Local : http://127.0.0.1:${PORT}"
echo "  LAN   : http://${IP}:${PORT}       <- open on phone/other PC"
echo "  Docs  : http://${IP}:${PORT}/docs"
echo "============================================================"
echo ""

exec .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}"
