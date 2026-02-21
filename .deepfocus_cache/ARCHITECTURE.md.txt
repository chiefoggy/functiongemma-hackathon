# Project Architecture Plan (Deep-Focus Library & Learning Hub)

This document plans the **project architecture** for the Deep-Focus library/learning-hub product, **building on top of the existing repo**. It assumes the current stack stays in place and new components are added alongside it.

---

## 1. Current Repository Layout (Existing)

```
functiongemma-hackathon/
├── main.py              # Hybrid brain: generate_cactus, generate_cloud, generate_hybrid, transcribe_audio
├── benchmark.py         # Eval harness (tool-call correctness, latency, edge/cloud ratio)
├── submit.py            # Leaderboard submission
├── .env / .env.sample   # GEMINI_API_KEY, CACTUS_API_KEY, etc.
├── cactus/              # Submodule: Cactus runtime, Python bindings, weights (FunctionGemma, Whisper)
├── backend/
│   ├── main.py          # FastAPI: CORS, /health, /api/chat, /api/transcribe; imports main.generate_*; finance tools today
│   ├── parsers.py       # PDF, DOCX, code, CSV, XLSX → text
│   ├── indexer.py       # Walk library root, parse, write to cache
│   ├── retrieval.py     # Search corpus by query
│   ├── scrubber.py      # Redact PII before cloud
│   └── requirements.txt # fastapi, uvicorn, python-multipart, yfinance, ...
├── frontend/            # Next.js app
│   ├── app/page.tsx     # Redirects / → /chat
│   ├── app/chat/page.tsx# Chat UI: messages, input, force-local toggle, metrics (source, confidence, latency)
│   └── next.config.ts   # Rewrites /api/* → http://localhost:8000/api/*
├── startup.sh           # Cactus clone/setup, venv, model download, backend startup
└── server_up.sh         # Start backend (uvicorn backend.main:app) + frontend (npm run dev)
```

**Current data flow (chat):**

1. User sends a message (and optional `force_local`) from the frontend.
2. `backend/main.py` receives POST `/api/chat`, appends to `conversation_history`, calls `generate_hybrid(conversation_history, FINANCE_TOOLS)` or `generate_cactus(...)`.
3. `main.py` routes: cognition/complex → `generate_cloud`, else → `generate_cactus`; confidence threshold decides fallback.
4. Backend runs **tool handlers** (e.g. get_stock_price, get_company_news) on the returned `function_calls`, builds a response (text + optional widgets), returns `{ response, metrics }`.
5. Frontend displays the reply and metrics (source, confidence, latency_ms).

**Existing primitives we keep:**

- `main.py`: `generate_cactus`, `generate_cloud`, `generate_hybrid`, `transcribe_audio`.
- Cactus: `cactus_init`, `cactus_complete`, `cactus_destroy`; optional `corpus_dir` for RAG (see Cactus README).
- Backend: FastAPI app, CORS, `/api/chat`, `/api/transcribe`.
- Frontend: Chat page, metrics, force-local.

---

## 2. New Product Scope (from SOLUTION.md)

- **User-specified root** = library and learning hub (one folder for syllabi, notes, PDFs, code, timelines).
- **Index** files under that root (PDF, DOC/DOCX, code, CSV, XLSX, Markdown, etc.), extract searchable text into a **corpus/cache**.
- **Answer questions** from that corpus: e.g. “Summarize the syllabus for this course”, “What’s the quiz timeline?”, “When are assignments due?” (assuming some file contains schedules).
- **Hybrid routing** unchanged: simple lookups/summaries on-device (local RAG + FunctionGemma), complex or low-confidence → Gemini (with optional privacy scrub).

---

## 3. Proposed Architecture (Layered on Top)

### 3.1 Config and environment

- **Library root path**: user-chosen directory for the hub (e.g. `~/StudyVault`, `./courses`).
  - Stored in backend (e.g. env `LIBRARY_ROOT` or `STUDY_VAULT_PATH`, or a small config file / DB later).
  - Frontend can expose a “Set library root” (and/or “Open folder”) and send it to the backend via a new API (e.g. `POST /api/config` or `PUT /api/library/root`).
- **Corpus/cache directory**: derived from library root or fixed (e.g. `./cache`, or `{LIBRARY_ROOT}/.deepfocus_cache`). All parsed text lives here so Cactus RAG and retrieval logic can read it.

### 3.2 New backend modules (under repo root or under `backend/`)

| Module | Responsibility |
|--------|----------------|
| **Parsers** | Given a file path, return plain text (or structured blobs) for indexing. Support: PDF, DOC/DOCX, code (.py, .js, .ts, .go, .md, …), CSV (e.g. first N rows → markdown table), XLSX (same). Use existing libs (e.g. PyMuPDF, python-docx, pandas). |
| **Indexer** | Walk `LIBRARY_ROOT`, filter by extension, call parsers, write results into the **corpus directory** (e.g. one .txt per file or chunk, or a format Cactus accepts). Optionally maintain a small manifest (file path → corpus path, mtime). |
| **File watcher** (optional) | Use `watchdog` to watch `LIBRARY_ROOT`; on change, re-run indexer for the changed file(s) and refresh corpus. |
| **Retrieval** | Given a user query, search the corpus (e.g. simple keyword/semantic search over parsed files, or rely on Cactus RAG if we init with `corpus_dir`). Return top-k chunks or file paths + snippets. |
| **Privacy scrubber** | Before sending a request to Gemini, redact configured keywords (names, IDs, etc.) from the message or retrieved context. |

### 3.3 Integration with existing `main.py` and Cactus

- **Option A – Cactus RAG**: Initialize Cactus with `cactus_init(functiongemma_path, corpus_dir=cache_dir)`. Then the **local** model can use the corpus for retrieval when answering. Tools in the backend could stay minimal (e.g. “answer from hub” as one tool that passes query + retrieved context).
- **Option B – Backend retrieval only**: Indexer writes to `cache_dir`; a **retrieval** layer in the backend (e.g. keyword search, or a small embedding search) fetches chunks. Backend then injects these chunks into the **prompt** or into a **tool** (e.g. `search_hub(query)` returns text; `summarize_syllabus()` returns summary from retrieved syllabus files). `main.py` stays unchanged; only the **tools** and **messages** passed to `generate_hybrid` change.

Recommendation: start with **Option B** (backend retrieval + tools) so we don’t depend on Cactus RAG behavior; later add Option A if we want Cactus to natively use the corpus.

### 3.4 Backend API and tools (building on current `backend/main.py`)

- **New/updated endpoints**:
  - `GET/PUT /api/library/root` — get or set the library root path (persist in env or config).
  - `POST /api/library/index` — trigger a full re-index of the library root (calls Indexer, writes to corpus/cache).
  - `GET /api/library/status` — return indexing status (e.g. last run, number of files, errors if any).
- **Chat flow** (still POST `/api/chat`):
  - **Tools** passed to `generate_hybrid` / `generate_cactus`: add **hub tools**, e.g.:
    - `search_hub(query: str)` — runs Retrieval over the corpus, returns top snippets (and optionally file paths). Handler in backend runs retrieval and returns text.
    - `summarize_from_hub(prompt: str)` — optional; retrieves relevant chunks, then either local summary or (if complex) can be routed to cloud with scrubber.
  - Tool **definitions** (name, description, parameters) stay in backend; **handlers** call the new Retrieval (and optionally Parsers/Indexer on demand). For “quiz timeline” or “assignment due dates”, the model can call `search_hub("quiz timeline")` or `search_hub("assignment due dates")`; the retrieval layer returns content from files that contain schedules (CSV, PDF tables, markdown lists, etc.).
- **Privacy scrubber**: in the path that builds the request for `generate_cloud`, optionally scrub the user message and any retrieved context before sending to Gemini.

### 3.5 Frontend (minimal changes on top of current chat)

- **Library root**:
  - Settings or onboarding: input for “Library root” path; save via `PUT /api/library/root`. Optional: “Index now” button → `POST /api/library/index` and show status from `GET /api/library/status`.
- **Chat**: no change to the core UX; user still types questions (e.g. “Summarize the syllabus for this course”, “What’s the quiz timeline?”). Backend uses the new hub tools and retrieval so answers come from the indexed hub; response and metrics (source, confidence, latency) stay as today.

### 3.6 Where each piece lives (summary)

| Component | Location | Notes |
|-----------|----------|--------|
| Library root config | Backend (env or config file); API: `/api/library/root` | |
| Parsers (PDF, DOC, code, CSV, XLSX) | New module e.g. `backend/parsers.py` or `lib/parsers/` | |
| Indexer (walk root, parse, write to cache) | New module e.g. `backend/indexer.py` or `lib/indexer.py` | |
| Corpus/cache directory | Under repo or under library root (e.g. `./cache`, `{root}/.deepfocus_cache`) | |
| Retrieval (search corpus) | New module e.g. `backend/retrieval.py` | Simple at first (keyword/snippet); optional embeddings later. |
| File watcher | Optional; e.g. `backend/watcher.py` or a small CLI | Uses `watchdog`. |
| Privacy scrubber | Backend, before calling `generate_cloud` | |
| Hub tools (search_hub, etc.) | `backend/main.py` (tool definitions + handlers) | Same pattern as current finance tools. |
| generate_hybrid / generate_cactus / generate_cloud | `main.py` (unchanged) | Still used by backend for every chat. |
| Chat UI + metrics | `frontend/app/chat/page.tsx` | Unchanged; optional “Library root” in settings. |
| Index trigger + status | Frontend: button + status from `/api/library/status` | |

---

## 4. Data Flow (End-to-End)

1. **Setup**: User sets library root (e.g. via frontend or env). Backend runs indexer once (or on demand): walk root → parse supported files → write parsed text into corpus directory.
2. **Optional**: File watcher keeps corpus in sync when files under the root change.
3. **Query**: User asks “What’s the quiz timeline?” in the chat.
4. **Backend**: Builds `messages` and a tools list that includes `search_hub`. Calls `generate_hybrid(messages, tools)`.
5. **main.py**: Routes to local or cloud as today. Suppose the model returns a tool call `search_hub("quiz timeline")`.
6. **Backend**: Runs the handler for `search_hub`: calls Retrieval with query `"quiz timeline"`, gets back chunks (e.g. from a CSV or markdown file that lists quiz dates). Returns those chunks (or a summary) as the tool result.
7. **Backend**: If the model needs more (e.g. “summarize”), it may call again or the backend may inject the retrieved chunks into the next message and re-call `generate_hybrid` / `generate_cloud`. For “summarize syllabus”, retrieval finds syllabus docs; either local or cloud (with scrubber) produces the summary.
8. **Response**: Backend formats the final answer and metrics (source, confidence, latency) and returns to the frontend; chat UI displays them as today.

---

## 5. Implementation Order (Suggested)

1. **Config + corpus path**: Add `LIBRARY_ROOT` (or equivalent) and a fixed or derived `cache_dir`; implement `GET/PUT /api/library/root` and ensure backend can read/write the corpus directory.
2. **Parsers**: Implement parsers for PDF, DOCX, code (read as text), CSV, XLSX → text/markdown; unit tests for one file per type.
3. **Indexer**: Walk library root, call parsers, write to `cache_dir`; expose `POST /api/library/index` and `GET /api/library/status`.
4. **Retrieval**: Simple search over corpus files (e.g. grep-like or small embedding index); implement `search_hub(query)` and wire it as a tool in `backend/main.py`.
5. **Hub tools in chat**: Add `search_hub` (and optionally `summarize_from_hub`) to the tools passed to `generate_hybrid`; implement handlers; test “quiz timeline” and “summarize syllabus” style queries.
6. **Privacy scrubber**: Add keyword list and redaction step before `generate_cloud`; optional API to configure keywords.
7. **Frontend**: Library root setting + “Index now” + status; keep chat as is.
8. **Optional**: File watcher; optional Cactus RAG (Option A) if we want the local model to use the corpus natively.

---

## 6. Files to Add or Touch (Checklist)

| Action | Path |
|--------|------|
| Add | `backend/parsers.py` (or `lib/parsers/`) |
| Add | `backend/indexer.py` (or `lib/indexer.py`) |
| Add | `backend/retrieval.py` |
| Add | `backend/scrubber.py` (optional) |
| Modify | `backend/main.py` (library endpoints, hub tools, scrubber in cloud path) |
| Add (optional) | `backend/watcher.py` |
| Modify | `frontend/app/chat/page.tsx` or add settings page (library root, index, status) |
| Add | Env or config: `LIBRARY_ROOT`, `DEEPFOCUS_CACHE_DIR` (or derive from root) |
| Unchanged | `main.py`, `benchmark.py`, `submit.py`, Cactus submodule |

This keeps the existing architecture (main.py hybrid, backend FastAPI, frontend Next.js chat) and layers the library hub (index, retrieve, answer, optional scrub and watcher) on top of it.
