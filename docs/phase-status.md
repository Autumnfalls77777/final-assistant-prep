# JARVIS Phase Status

## Current Phase

Phase 3 — Persistent Memory

**Implementation status:** Phases 0–3 are implemented and locally verified. Phase 2's live cloud/local provider path is blocked by missing provider configuration, but its routing and tool-calling path is covered by deterministic integration tests.  
**Authorization:** Phases 0–3 were authorized by the owner.  
**Owner sign-off:** Pending. This file does not mark any phase as owner-verified.

| Phase | Status | Local verification |
|---|---|---|
| Phase 0 — Foundation | Implemented | Passed |
| Phase 1 — Tool registry | Implemented | Passed |
| Phase 2 — AI orchestration | Implemented; live provider check blocked | Deterministic integration passed |
| Phase 3 — Persistent memory | Implemented | Passed, including restart persistence |
| Phase 4 — Desktop interface | Not started | Pending |

---

## Phase 0 — Foundation

**Status:** Implemented and locally verified. Owner sign-off pending.

### Completed

- [x] Repository structure established for the Python backend.
- [x] Isolated `.venv` created; project dependencies installed from `pyproject.toml`.
- [x] Configuration loaded from the root `.env` and validated with Pydantic Settings.
- [x] Loopback-only API host validation; non-loopback addresses are rejected.
- [x] Port, log level, environment, and IANA timezone validation.
- [x] FastAPI application factory and `python -m jarvis` entry point.
- [x] `GET /health` endpoint that requires no model credentials or network services.
- [x] Standard-library logging with an idempotent handler.
- [x] pytest test suite.
- [x] `.gitignore` protecting `.env`, the virtual environment, caches, local data, and future frontend artifacts.
- [x] `.env.example` with safe placeholders only.
- [x] Root `README.md` with setup, run, test, and security instructions.

---

## Phase 1 — Tool Registry and Windows Automation

**Status:** Implemented and locally verified. Owner sign-off pending.

### Completed

- [x] Typed tool interface with validated input and output schemas.
- [x] Risk levels: `READ`, `LOW`, `CONFIRM`, `CRITICAL`.
- [x] Permission policy that auto-allows only `READ` tools.
- [x] Confirmation-required and denied tools are not executed.
- [x] Tool registry with duplicate-name rejection and deterministic discovery.
- [x] Per-tool timeouts enforced with `asyncio.wait_for`.
- [x] Structured tool results and stable error codes.
- [x] JSONL audit logging with key-based redaction and long-string truncation.
- [x] Read-only Windows tools:
  - `get_system_info`
  - `get_disk_usage`
  - `list_processes`
  - `get_battery_status`
- [x] Tool discovery endpoint: `GET /tools`.
- [x] Tool execution endpoint: `POST /tools/{tool_name}/execute`.
- [x] Tools remain in the separate `backend/src/jarvis/tools/` package and are registered at application startup by `build_default_registry()` in `main.py`.

---

## Phase 2 — AI Orchestration

**Status:** Implemented; deterministic integration tests pass. Live Gemini verification is blocked by a missing `GEMINI_API_KEY`. Live Ollama verification is blocked by the local service failing to start. Owner sign-off pending.

### Completed

- [x] Direct Gemini `generateContent` adapter using `httpx`.
  - API key sent in the `x-goog-api-key` header, not the URL.
  - Function declarations use a Gemini-compatible JSON-schema subset.
  - Function calls and function responses are normalized.
- [x] Direct Ollama `/api/chat` adapter.
  - Supports text and tool calls.
  - Health check uses `/api/tags` and reports a missing configured model.
- [x] Provider-neutral chat/tool schemas.
- [x] `ModelRouter` with:
  - Gemini as the default primary provider.
  - Optional Ollama fallback when Gemini fails.
  - Runtime provider switching through the API.
  - Safe provider health reporting without exposing credentials.
- [x] Gemini primary / Ollama fallback behavior is covered by deterministic tests.
- [x] Bounded tool-calling orchestrator:
  - Executes tools only through the existing permissioned registry.
  - Feeds structured tool results back to the model.
  - Enforces maximum tool iterations and maximum tool calls.
  - Returns the provider used, providers attempted, tool results, and execution verification.
  - Adds a factual warning when a tool fails.
- [x] Chat endpoint: `POST /chat`.
- [x] Model discovery endpoint: `GET /models`.
- [x] Runtime selection endpoint: `PUT /models/active`.
- [x] System prompt treats tool output as untrusted data and prohibits claiming an unverified success.
- [x] Phase 3 memory context is retrieved before the model call and bounded before insertion into the prompt.

### Phase 2 verification

The orchestration acceptance path was verified with deterministic provider doubles:

```text
User request
  -> provider selects a registered READ tool
  -> registry validates and executes it
  -> structured result is returned to the provider
  -> final answer is returned with execution_verified=true
```

Failure paths verified:

- Unknown tool -> structured `not_found`, `execution_verified=false`.
- Permission-denied tool -> structured `permission_denied`, not executed.
- Gemini failure -> Ollama fallback when enabled.
- Both providers fail -> `503`, no fabricated answer.
- Tool-call and iteration limits stop the loop truthfully.

### Live provider limitation

The live `.env` currently has no `GEMINI_API_KEY`. The model status endpoint therefore truthfully reports:

```text
gemini: configured=false, available=false
ollama: configured=true, available=false (Ollama is not reachable)
```

Ollama is installed, but starting its service currently fails with a Windows paging-file error. No local model could be pulled or tested. The `/chat` endpoint returned `503` rather than inventing a response. This is the correct safe behavior.

---

## Phase 3 — Persistent Memory

**Status:** Implemented and locally verified, including a restart persistence check. Owner sign-off pending.

### Completed

- [x] SQLite-backed local memory store at `MEMORY_DB_PATH`.
- [x] Memory kinds: `personal`, `project`, `episodic`, `working`, `semantic`.
- [x] Structured records with:
  - Source, confidence, project, optional key, metadata.
  - Created/updated/accessed timestamps.
  - Expiry, supersession, and active state.
- [x] Local deterministic hashing embeddings (384 dimensions, unigrams + bigrams).
- [x] Vector retrieval combined with lexical token coverage.
- [x] Bounded retrieval results and bounded memory context length.
- [x] Exact-content deduplication.
- [x] Keyed correction that supersedes the previous active value.
- [x] Working-memory TTL and startup expiry cleanup.
- [x] Retention cleanup for stale superseded records.
- [x] Content-free memory audit events.
- [x] Hard deletion of memory content while retaining an event without content.
- [x] Automatic episodic memory storage for completed chat turns.
- [x] Memory inspection and export.
- [x] API endpoints:
  - `POST /memory`
  - `GET /memory`
  - `GET /memory/search`
  - `GET /memory/stats`
  - `GET /memory/events`
  - `GET /memory/export`
  - `GET /memory/{memory_id}`
  - `PATCH /memory/{memory_id}`
  - `DELETE /memory/{memory_id}`

### Phase 3 verification

- Unit tests cover persistence, deduplication, keyed supersession, retrieval relevance, filtering, expiry, correction, deletion, stats, events, export, and prompt-context bounds.
- Live server check created a memory, searched for it, corrected it, created a second memory, restarted the backend, and confirmed both records survived.
- The live search for `persistence` returned the persisted record.
- The live DELETE returned `204`.
- The live server was stopped after verification; its database and audit files were kept outside the repository.

---

## Final Automated Checks

At the time of this update:

```text
pytest -q                        106 passed
ruff check .                     All checks passed
ruff format --check .            54 files already formatted
mypy                             Success: no issues found in 38 source files
pip check                        No broken requirements found
```

Live loopback checks:

```text
GET  /health                              200, status=ok
GET  /tools                               200, 4 read-only tools
POST /tools/get_system_info/execute       200, ok=true
GET  /models                              200, Gemini unconfigured; Ollama unreachable
POST /chat                                503, no provider available; no fabricated answer
POST /memory                              201, record created
GET  /memory/search?q=preferred%20editor  200, relevant record returned
PATCH /memory/{id}                        200, correction persisted
Restart backend                           memory records persisted
DELETE /memory/{id}                       204
```

The live server was loopback-bound and was not exposed publicly.

---

## Changed Files

### Phase 2

- `backend/src/jarvis/models/schemas.py`
- `backend/src/jarvis/models/base.py`
- `backend/src/jarvis/models/errors.py`
- `backend/src/jarvis/models/gemini.py`
- `backend/src/jarvis/models/ollama.py`
- `backend/src/jarvis/models/router.py`
- `backend/src/jarvis/models/factory.py`
- `backend/src/jarvis/models/prompts.py`
- `backend/src/jarvis/models/orchestrator.py`
- `backend/src/jarvis/api/chat.py`
- `backend/src/jarvis/api/models.py`
- `backend/src/jarvis/main.py`
- `backend/src/jarvis/config.py`
- `pyproject.toml` (added `httpx`)
- `backend/tests/test_gemini_provider.py`
- `backend/tests/test_ollama_provider.py`
- `backend/tests/test_model_router.py`
- `backend/tests/test_orchestrator.py`
- `backend/tests/test_chat_api.py`

### Phase 3

- `backend/src/jarvis/memory/schemas.py`
- `backend/src/jarvis/memory/embeddings.py`
- `backend/src/jarvis/memory/service.py`
- `backend/src/jarvis/memory/__init__.py`
- `backend/src/jarvis/api/memory.py`
- `backend/src/jarvis/main.py`
- `backend/src/jarvis/config.py`
- `backend/tests/test_memory_service.py`
- `backend/tests/test_memory_api.py`
- `backend/tests/support.py`

### Documentation and configuration

- `README.md`
- `.env.example`
- `docs/phase-status.md`
- `docs/README.md` status banner

### Preserved

- `.env` — not modified, not committed.
- `AGENTS.md`
- `opencode.json`
- `.opencode/skills/*/SKILL.md`

---

## Known Issues and Limitations

1. **Owner sign-off is pending** for Phases 0–3. Local implementation verification does not equal owner acceptance.
2. **Gemini live validation is blocked** because no `GEMINI_API_KEY` is configured. The adapter and routing are tested with deterministic doubles.
3. **Ollama live validation is blocked** because the installed service fails to start with a Windows paging-file error. No model could be pulled or run.
4. **Runtime provider selection is in-memory only.** It resets to `DEFAULT_MODEL_PROVIDER` when the backend restarts.
5. **No streaming responses.** `/chat` waits for a complete model response.
6. **Memory embeddings are lightweight lexical hashing embeddings**, not a deep semantic model. Retrieval is brute-force over up to 2,000 active records. The embedder interface can be replaced later.
7. **Retention cleanup runs at startup**, not on a scheduled background job.
8. **Chat episode auto-storage is enabled by default.** It can be disabled with `MEMORY_AUTO_STORE_CHAT=false`.
9. **The local API is unauthenticated but loopback-bound.** Remote authentication and authorization remain Phase 8 work.
10. **Only `READ` tools are auto-allowed.** `LOW`, `CONFIRM`, and `CRITICAL` tools are denied because no confirmation channel exists yet.
11. **Desktop UI is not implemented yet.** Phase 4 remains next.
12. **Rust/Tauri installation failed locally** with installer exit code `3221225786` (`STATUS_DLL_INIT_FAILED`). This must be resolved before a real Tauri window can be built.
13. `docs/README.md` is still an incomplete product-vision draft; the root `README.md` and this file are authoritative for current setup and status.

---

## Next Task

Phase 4 — Desktop interface:

- Tauri 2 + React + TypeScript + Vite.
- Floating orb, sidebar, chat, command input, activity feed, system status.
- Memory, Automations, and Settings screens.
- Demo interactions without real AI calls.
- Backend communication only for non-AI status/health where safe.
- Verify the real Windows desktop window launches.

Do not begin Phase 5 voice work until Phase 4 is verified.

## Owner Approval

- Phase 0: **Authorized; local verification complete; owner sign-off pending.**
- Phase 1: **Authorized; local verification complete; owner sign-off pending.**
- Phase 2: **Authorized; implementation verified with deterministic providers; live provider validation blocked; owner sign-off pending.**
- Phase 3: **Authorized; local verification and restart persistence complete; owner sign-off pending.**
