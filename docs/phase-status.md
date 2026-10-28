# JARVIS Phase Status

## Current Phase

Phase 4 — Desktop Interface

**Implementation status:** Phases 0–3 are implemented and locally verified. The Phase 4 browser UI is implemented and live-verified against Gemini. The native Tauri window is still blocked by the local Windows toolchain.  
**Authorization:** Phases 0–3 were authorized by the owner. Phase 4 browser UI work was requested by the owner.  
**Owner sign-off:** Pending. This file does not mark any phase as owner-verified.

| Phase | Status | Local verification |
|---|---|---|
| Phase 0 — Foundation | Implemented | Passed |
| Phase 1 — Tool registry | Implemented | Passed |
| Phase 2 — AI orchestration | Implemented; Gemini live-verified | Deterministic integration and live chat passed |
| Phase 3 — Persistent memory | Implemented | Passed, including restart persistence |
| Phase 4 — Desktop interface | Browser UI implemented; native Tauri blocked | Browser/live verification passed; Tauri pending |

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

**Status:** Implemented; deterministic integration and live Gemini verification pass. Live Ollama verification is blocked by the local service failing to start. Owner sign-off pending.

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

### Live provider verification

Live Gemini verification passed with `gemini-3-flash-preview`:

```text
GET  /models   active_provider=gemini, configured=true, available=true
POST /chat     provider=gemini, reply returned, execution path verified
GET  /usage    provider=gemini, request and token counts updated
```

The browser UI also completed a live Gemini turn and displayed the reply, token count, and updated local usage meter.

Ollama is installed, but starting its service currently fails with a Windows paging-file error. No local model could be pulled or tested. When both providers are unavailable, `/chat` returns `503` rather than inventing a response.

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
- The live server was stopped after verification; its database and audit files were kept out of version control.

---

## Phase 4 — Desktop Interface

**Status:** Browser UI implemented and live-verified. The native Tauri window remains blocked by the local Windows toolchain. Owner sign-off pending.

### Completed

- [x] React + TypeScript + Vite desktop source in `desktop/`.
- [x] Single-screen JARVIS layout instead of a sidebar/dashboard mockup.
- [x] Hollow glass orb rendered with plain CSS.
- [x] Particle field flowing around the hollow shell.
- [x] Runtime visual states: idle, listening, thinking, and responding/speaking.
- [x] Chat composer and conversation stream connected to `POST /chat`.
- [x] Assistant reply typewriter rendering and speaking state.
- [x] Live Gemini provider/model status in the top bar.
- [x] Provider token usage display per assistant turn.
- [x] Local daily usage meter backed by `GET /usage` and `var/usage.db`.
- [x] Honest local-budget labeling: the meter is not presented as Google quota.
- [x] Desktop-only CORS allowlist for the Vite and Tauri origins.
- [x] Performance pass:
  - Removed full-screen noise and large backdrop blurs.
  - Removed animated blur filters.
  - Kept orb animation to transform/opacity properties.
  - Removed per-character smooth scrolling.
  - Reduced typewriter update pressure and memoized static orb and meter components.
- [x] Responsive layout for narrower desktop windows.

### Phase 4 verification

- Backend tests: `113 passed`.
- Ruff, Ruff format, mypy, and `pip check` passed.
- `npm run build` passed.
- Browser verification used headless Chrome against `http://localhost:1420`.
- Final idle pass verified the hollow shell, 15 particles, the one-decimal local usage label, a data-URI favicon, and no console/HTTP errors.
- Live browser turn:
  - Link state: `LINK ONLINE`.
  - Thinking state observed.
  - Speaking state observed.
  - Reply: `BROWSER LINK OK`.
  - Assistant usage: `683 tokens`.
  - `/usage` refreshed to the new total.
- The test-only local usage ledger was reset after verification; normal usage starts at zero for the current local day.

### Native window limitation

The real Tauri window cannot yet be built locally:

- Visual Studio C++ Build Tools/MSVC and the Windows SDK are missing.
- `C:` free space is low and the paging file is on `C:`.
- The Rust linker fails at the `windows-sys`/`dlltool` step.

The browser UI is verified; do not claim the native Tauri window works until the toolchain is repaired.

---

## Final Automated Checks

At the time of this update:

```text
pytest -q                        113 passed
ruff check .                     All checks passed
ruff format --check .            67 files already formatted
mypy                             Success: no issues found in 40 source files
pip check                        No broken requirements found
npm run build                    Passed (desktop)
```

Live checks:

```text
GET  /health                              200, status=ok
GET  /tools                               200, 4 read-only tools
POST /tools/get_system_info/execute       200, ok=true
GET  /models                              200, Gemini configured and available
POST /chat                                200, provider=gemini, live reply returned
GET  /usage                               200, local ledger updated
Browser UI                                LINK ONLINE, thinking/speaking observed
Browser reply                             BROWSER LINK OK
Browser turn usage                        683 tokens
POST /memory                              201, record created
GET  /memory/search?q=preferred%20editor  200, relevant record returned
PATCH /memory/{id}                        200, correction persisted
Restart backend                           memory records persisted
DELETE /memory/{id}                       204
```

Ollama remained unavailable during live verification because its local service cannot start under the current paging-file limits. The live server was loopback-bound and was not exposed publicly.

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

### Phase 4 and token usage

- `backend/src/jarvis/usage.py`
- `backend/src/jarvis/api/usage.py`
- `backend/src/jarvis/models/schemas.py`
- `backend/src/jarvis/models/gemini.py`
- `backend/src/jarvis/models/ollama.py`
- `backend/src/jarvis/models/orchestrator.py`
- `backend/src/jarvis/main.py`
- `backend/src/jarvis/config.py`
- `backend/tests/test_usage.py`
- `backend/tests/test_chat_api.py`
- `backend/tests/test_gemini_provider.py`
- `backend/tests/test_ollama_provider.py`
- `backend/tests/test_orchestrator.py`
- `backend/tests/test_config.py`
- `backend/tests/test_health.py`
- `backend/tests/conftest.py`
- `desktop/src/App.tsx`
- `desktop/src/styles.css`
- `desktop/src/lib/api.ts`
- `desktop/src/components/BlobOrb.tsx`
- `desktop/src/components/UsageMeter.tsx`
- `desktop/src/components/WindowChrome.tsx`
- `desktop/src/components/Icon.tsx`
- `desktop/src/main.tsx`
- `desktop/index.html`
- `desktop/package.json`
- `desktop/vite.config.ts`
- `desktop/src-tauri/` (scaffold; native launch pending)
- `start.md`

### Documentation and configuration

- `README.md`
- `.env.example`
- `.gitignore`
- `docs/phase-status.md`
- `docs/README.md` status banner

### Preserved

- `.env` — not modified, not committed.
- `AGENTS.md`
- `opencode.json`
- `.opencode/skills/*/SKILL.md`

---

## Known Issues and Limitations

1. **Owner sign-off is pending** for Phases 0–4. Local implementation verification does not equal owner acceptance.
2. **Gemini live validation passed** with `gemini-3-flash-preview`. Preview model names may change or be retired; update `GEMINI_MODEL` if the provider reports it unavailable.
3. **Ollama live validation is blocked** because the installed service fails to start with a Windows paging-file error. No model could be pulled or run.
4. **The usage meter is a local budget ledger**, not Google’s live quota. Gemini API keys do not expose remaining quota through this API.
5. **Runtime provider selection is in-memory only.** It resets to `DEFAULT_MODEL_PROVIDER` when the backend restarts.
6. **No streaming responses.** `/chat` waits for a complete model response; the UI then reveals the reply with a lightweight typewriter effect.
7. **Memory embeddings are lightweight lexical hashing embeddings**, not a deep semantic model. Retrieval is brute-force over up to 2,000 active records. The embedder interface can be replaced later.
8. **Retention cleanup runs at startup**, not on a scheduled background job.
9. **Chat episode auto-storage is enabled by default.** It can be disabled with `MEMORY_AUTO_STORE_CHAT=false`.
10. **The local API is unauthenticated but loopback-bound.** Remote authentication and authorization remain Phase 8 work.
11. **Only `READ` tools are auto-allowed.** `LOW`, `CONFIRM`, and `CRITICAL` tools are denied because no confirmation channel exists yet.
12. **The browser UI is implemented and verified; the native Tauri window is not.** Rust/Tauri installation failed locally with installer exit code `3221225786` (`STATUS_DLL_INIT_FAILED`), and MSVC/Windows SDK components are incomplete.
13. **“Listening” is visual only.** The UI reacts to chat-input focus and typing; microphone capture and speech recognition remain Phase 5 work.
14. **The orb/UI performance pass is transform/opacity based.** Large blur and backdrop-filter effects are intentionally avoided to keep the browser preview smooth.
15. `docs/README.md` is still an incomplete product-vision draft; the root `README.md` and this file are authoritative for current setup and status.

---

## Next Task

Finish Phase 4 native packaging once the Windows toolchain is repaired:

- Install Visual Studio C++ Build Tools and the Windows SDK.
- Resolve the low `C:` free-space and paging-file constraint.
- Launch `npm run tauri dev` and verify the real Windows desktop window.
- Do not add a sidebar/dashboard layout; the owner-approved direction is the single-screen orb plus chat dock.
- Do not begin Phase 5 voice work until Phase 4 native launch is verified or the owner explicitly accepts the browser UI as the interim Phase 4 deliverable.

## Owner Approval

- Phase 0: **Authorized; local verification complete; owner sign-off pending.**
- Phase 1: **Authorized; local verification complete; owner sign-off pending.**
- Phase 2: **Authorized; deterministic and live Gemini verification complete; owner sign-off pending.**
- Phase 3: **Authorized; local verification and restart persistence complete; owner sign-off pending.**
- Phase 4: **Browser UI implemented and live-verified; native Tauri launch pending; owner sign-off pending.**
