# AGENTS.md

## Quick Start

```bash
# Windows
run.bat

# macOS / Linux
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit at least DEMO_API_KEY
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

App serves at http://127.0.0.1:8000. First boot auto-downloads BGE embedding model and seeds demo docs from `sample_docs/`.

## Architecture

Single-package FastAPI app. No monorepo, no package manager beyond pip.

```
app/
  main.py          # FastAPI entrypoint, all route definitions
  config.py        # env-driven config, reload_config() called at import time
  models.py        # Pydantic request/response models
  services/
    rag.py         # retrieve + ask/ask_stream pipeline
    embedder.py    # embedding backend switch (keyword/fastembed/flag)
    llm.py         # LLM provider abstraction (OpenAI compat / Ollama / retrieval-only)
    app_mode.py    # tier resolution (full/demo/retrieval), demo quota
    ingest.py      # document upload + chunk + vectorize pipeline
    reranker.py    # LLM-based reranking
    relevance.py   # scoring functions (semantic, keyword, combined)
    chunk_enricher.py  # heading path + AI summary enrichment per chunk
    document_parser.py # file format parsing via MarkItDown
    demo_seed.py   # startup demo data seeding
    settings_manager.py # runtime settings persistence
    embedding_migrate.py # embedding index migration on startup
  storage/
    vector_store.py # ChromaDB wrapper
    workspaces.py   # workspace CRUD (JSON file persistence)
static/            # single-page frontend (vanilla JS, no build step)
data/              # runtime: ChromaDB, uploads, quotas (git-ignored, must be persistent)
sample_docs/       # demo documents, auto-imported on first boot
```

## Key Facts

- **Python 3.12** required (used in Dockerfile and type hints use `str | None`)
- **No test suite, linter, or typechecker** is configured in this repo
- **No pre-commit hooks** or CI workflows exist
- `.env` is git-ignored; never commit real API keys
- `data/` is git-ignored; must be mounted as persistent volume in production
- Docker default: `EMBEDDING_BACKEND=keyword`, `INGEST_ENABLE_SUMMARY=true`

## Three Run Modes

| Mode | Trigger | LLM | Reranking |
|------|---------|-----|-----------|
| Full | User sets API key in browser | User's key | Yes |
| Demo | `DEMO_API_KEY` set server-side | Server key (default DeepSeek) | No |
| Retrieval | No key available | None | No |

User API keys are stored in browser `localStorage` and sent via `X-User-Api-Key` header. Server `.env` keys are never exposed to the client.

## Embedding Backends

Set via `EMBEDDING_BACKEND` env var:

| Backend | Memory | Notes |
|---------|--------|-------|
| `keyword` | Minimal | Chinese keyword overlap, no model download |
| `fastembed` | ~1.5 GB | ONNX-based, downloads model on first boot |
| `flag` | 2 GB+ | FlagEmbedding BGE, requires `requirements-full.txt` |

**Do not** use `flag` on 1 GB Railway instances. Use `keyword` for free-tier demos.

## Gotchas

- Config values are loaded at import time via `reload_config()` in `config.py`. Changing `.env` requires a restart.
- `EMBEDDING_BACKEND` is read once at startup and cached; switching backends requires restart + vector store rebuild.
- `data/chroma/` stores the vector DB. Deleting it loses all indexed documents.
- `data/demo_quotas.json` tracks demo rate limits per IP+session. Safe to delete (resets quotas).
- The `keyword` backend uses dummy vectors (not real embeddings). Scoring is pure keyword overlap.
- Demo mode has per-IP daily limit (`DEMO_DAILY_LIMIT`) and per-minute rate limit (`DEMO_PER_MINUTE_LIMIT`).
- Document upload limit: 20 MB per file. Supported formats: TXT, MD, PDF, DOCX, PPTX, XLSX.
- `ALLOW_ENV_KEY_WRITE=false` prevents users from modifying server-side API keys via the settings UI.

## Deployment

- **Railway**: Mount volume at `/app/data`, set `EMBEDDING_BACKEND=keyword` for free tier
- **Docker**: `docker build -t knowledgeqa . && docker run -p 8000:8000 --env-file .env -v knowledgeqa-data:/app/data knowledgeqa`
- Health check endpoint: `GET /api/health` (returns `startup_ready: true` when initialization completes)
