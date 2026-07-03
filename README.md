# 🎧 AI Customer Support Assistant

A **fully offline**, **multilingual** (Japanese ⇄ English) AI assistant that helps
customer‑support representatives answer faster — with **document‑grounded**,
**non‑hallucinating** suggested replies, confidence scores, and source citations.

> The assistant **never** messages customers directly. It only assists the human agent.

---

## ✨ Highlights

- **100% local / offline** — Ollama + Gemma 3, local Qdrant, local SQLite. No Google, no OpenAI, no cloud.
- **Multilingual** — auto language detection, JA→EN internal translation, EN→JA reply translation.
- **RAG over your documents** — PDF, DOCX, TXT, CSV, Excel, Markdown.
- **Conversation memory** — semantic search over past chats.
- **Top‑3 grounded suggestions** — each with confidence, referenced docs, pages, and reasoning.
- **No‑hallucination policy** — replies "I could not find supporting information…" when unsupported.
- **Neobrutalism UI** — bold borders, strong shadows, yellow/blue/pink, dark & light mode.
- **Optimized for Apple Silicon** — M1 / 8GB RAM friendly.

---

## 🧱 Tech Stack

| Layer        | Technology                                             |
|--------------|--------------------------------------------------------|
| Frontend     | React · Vite · TypeScript · TailwindCSS · Neobrutalism |
| Backend      | FastAPI (async) · Python 3.11+                          |
| LLM          | Ollama · **Gemma 3 (4B)** (`gemma3:4b`)                 |
| Embeddings   | `nomic-embed-text`                                     |
| Vector DB    | Qdrant (local / embedded)                              |
| Database     | SQLite (async via SQLAlchemy)                          |
| Translation  | NLLB‑200 (optional) · Gemma prompt (default)          |

---

## 📁 Project Structure

```
helpdesk/
├── backend/
│   ├── api/            # FastAPI routers (upload, chat, history, analytics, ...)
│   ├── services/       # Business logic (orchestration, DI)
│   ├── rag/            # Chunking, retrieval, hybrid search, prompt building
│   ├── llm/            # Ollama / Gemma client
│   ├── embeddings/     # nomic-embed-text client
│   ├── translation/    # NLLB-200 + Gemma fallback
│   ├── database/       # SQLAlchemy models & session
│   ├── qdrant/         # Vector store wrapper
│   ├── models/         # Pydantic schemas
│   ├── utils/          # Logging, system checks, helpers
│   ├── config/         # Settings (pydantic-settings)
│   ├── main.py         # FastAPI entrypoint
│   └── requirements.txt
├── frontend/           # React + Vite app (Phase 2)
├── uploads/            # Uploaded source documents
├── history/            # Exported conversations
├── data/
│   ├── qdrant/         # Local Qdrant storage
│   └── sqlite/         # SQLite database file
├── logs/               # Rotating application logs
├── tests/              # Pytest suite
├── .env.example        # Environment template
├── Makefile            # Dev commands
└── README.md
```

---

## ✅ Prerequisites

- **macOS (Apple Silicon)** — tested on MacBook Air M1 / 8GB.
- **Python 3.11+** (this repo uses `python3.12` via Homebrew).
- **Node.js 18+** and **npm**.
- **[Ollama](https://ollama.com)** installed and running.

### Pull the local models

```bash
ollama pull gemma3:4b
ollama pull nomic-embed-text
```

---

## 🚀 Quick Start (one command)

```bash
./run.sh
```

This installs deps (first run), pulls the models if missing, builds the frontend,
and serves the **whole app + API on a single port** at `http://0.0.0.0:8000`.
The script prints your **LAN URL** so you can open it on a phone or another PC.

### Manual setup

```bash
make setup            # python3.12 venv + backend deps
make models           # pull gemma3:4b + nomic-embed-text
make frontend-install # npm install
```

### Development mode (hot reload)

```bash
./dev.sh              # backend :8000 (reload) + Vite dev :5173 (LAN)
```

Verify:

```bash
curl http://127.0.0.1:8000/api/health   # {"status":"ok"}
curl http://127.0.0.1:8000/api/system   # Ollama + model availability
```

---

## 🌐 LAN Access

Both `run.sh` and `dev.sh` print the LAN URLs, or run:

```bash
make lan
```

- **Production (single port):** `http://<your-mac-ip>:8000`
- **Dev frontend:** `http://<your-mac-ip>:5173`  ·  **Dev API:** `http://<your-mac-ip>:8000`

Open the URL on any device on the same Wi‑Fi. (On macOS you may need to allow
incoming connections for Python the first time.)

---

## ⚡ Performance notes (M1 / 8GB)

- Async FastAPI, batch embeddings, in‑process caching, Qdrant HNSW, bounded
  generation tokens, and a background **model warmup** on startup.
- First query after boot is slower (model load); subsequent replies are faster
  because the model is kept warm (`LLM_KEEP_ALIVE`). Realistic warm latency for
  Top‑3 grounded generation on an M1/8GB is ~15–25s for `gemma3:4b`. For snappier
  replies you can switch to `gemma3:1b` in **Settings** (trades some quality).

---

## 🔌 API Endpoints

| Method | Path | Purpose |
|-------:|------|---------|
| POST | `/api/upload` | Upload & ingest a document |
| POST | `/api/chat` | Get Top‑3 grounded suggestions |
| GET  | `/api/history` | List / search conversations |
| POST | `/api/translate` | JA ⇄ EN translation |
| POST | `/api/products` | Grounded product search |
| GET  | `/api/analytics` | Dashboard statistics |
| DELETE | `/api/documents/{id}` | Delete a document + embeddings |
| GET | `/api/models`, POST `/api/models/select` | List / switch LLM |

---

## 🗺️ Build Roadmap

| Phase | Deliverable                         | Status  |
|------:|-------------------------------------|---------|
| 1     | Project setup                       | ✅ Done |
| 2     | Frontend (Neobrutalism UI)          | ✅ Done |
| 3     | Backend (FastAPI core)              | ✅ Done |
| 4     | Document upload & ingestion         | ✅ Done |
| 5     | Qdrant integration                  | ✅ Done |
| 6     | RAG pipeline                        | ✅ Done |
| 7     | Translation                         | ✅ Done |
| 8     | Chat                                | ✅ Done |
| 9     | Previous conversation retrieval     | ✅ Done |
| 10    | Top‑3 AI suggestions                | ✅ Done |
| 11    | Analytics dashboard                 | ✅ Done |
| 12    | Optimization                        | ✅ Done |
| 13    | Testing                             | ✅ Done |
| 14    | Deployment + LAN link               | ✅ Done |

---

## 🔒 Privacy

Every component — LLM, embeddings, vector search, translation, and storage —
runs on your machine. **No data ever leaves your device.**
