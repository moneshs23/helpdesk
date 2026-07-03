# ============================================================
#  AI Customer Support Assistant — developer commands
# ============================================================
PY ?= python3.12
VENV := .venv
BIN := $(VENV)/bin

.PHONY: help setup backend-install backend frontend-install frontend dev models test lan clean

help:
	@echo "Targets:"
	@echo "  make setup            Create venv + install backend deps"
	@echo "  make backend          Run FastAPI (http://0.0.0.0:8000)"
	@echo "  make frontend-install Install frontend deps"
	@echo "  make frontend         Run Vite dev server (host mode / LAN)"
	@echo "  make models           Pull required Ollama models (gemma3:4b, nomic-embed-text)"
	@echo "  make test             Run backend tests"
	@echo "  make lan              Print LAN URLs for phone/other devices"

setup: backend-install

$(VENV):
	$(PY) -m venv $(VENV)

backend-install: $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r backend/requirements.txt

backend:
	$(BIN)/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

frontend-install:
	cd frontend && npm install

frontend:
	cd frontend && npm run dev -- --host

dev:
	@echo "Run 'make backend' and 'make frontend' in two terminals."

models:
	ollama pull gemma3:4b
	ollama pull nomic-embed-text

test:
	$(BIN)/pytest -q

lan:
	@IP=$$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null); \
	echo "Frontend : http://$$IP:5173"; \
	echo "Backend  : http://$$IP:8000"; \
	echo "API docs : http://$$IP:8000/docs"

clean:
	rm -rf $(VENV) frontend/node_modules
