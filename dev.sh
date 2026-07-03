#!/usr/bin/env bash
# ============================================================
#  Development mode: backend (8000) + Vite dev server (5173)
#  Both bind to 0.0.0.0 for LAN access. Ctrl-C stops both.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 127.0.0.1)"

echo "==> Starting backend on http://0.0.0.0:8000"
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACK=$!

cleanup() { echo "Stopping..."; kill "$BACK" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo ""
echo "============================================================"
echo "  Frontend (dev) : http://${IP}:5173     <- use this in the browser"
echo "  Backend  (API) : http://${IP}:8000"
echo "============================================================"
echo ""

cd frontend && npm run dev -- --host
