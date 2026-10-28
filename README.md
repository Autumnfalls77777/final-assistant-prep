# JARVIS

A modular, local-first personal AI assistant for Windows.

**Current implementation:** Phases 0–3 — foundation, read-only tools, Gemini/Ollama orchestration, and persistent local memory. The Phase 4 browser UI is implemented and live-verified against Gemini; the native Tauri shell is still blocked by the local Windows toolchain.  
**Owner sign-off:** Pending. Local implementation and live Gemini verification are complete.

## Current scope

The backend currently provides:

- Validated configuration loaded from the project `.env`.
- A loopback-only FastAPI service.
- `GET /health` liveness checks that require no AI credentials.
- A typed tool registry with permission checks, timeouts, structured errors, and JSONL audit logging.
- Four read-only Windows system tools:
  - `get_system_info`
  - `get_disk_usage`
  - `list_processes`
  - `get_battery_status`
- Tool discovery through `GET /tools`.
- Explicit tool execution through `POST /tools/{tool_name}/execute`.
- Gemini and Ollama provider adapters behind a common interface.
- Gemini primary with optional Ollama fallback.
- Runtime provider discovery and selection:
  - `GET /models`
  - `PUT /models/active`
- A bounded tool-calling orchestrator through `POST /chat`.
- Truthful execution evidence: tool results, failure warnings, and `execution_verified`.
- SQLite-backed memory with `personal`, `project`, `episodic`, `working`, and `semantic` records.
- Local hashing embeddings and vector-plus-lexical retrieval.
- Memory deduplication, correction, expiry, retention cleanup, inspection, export, and deletion.
- Memory endpoints under `/memory`.
- Automatic episodic storage of completed chat turns.
- A browser-verified React desktop UI in `desktop/`:
  - Single animated JARVIS orb with idle, listening, thinking, and speaking states.
  - Live chat through the backend and Gemini.
  - Real provider token counts and a persistent local daily usage meter.
  - Focused desktop layout with a narrow CORS allowlist.

The following are intentionally **not** implemented yet:

- Native Tauri window packaging — the browser UI is ready, but the local MSVC/Windows SDK toolchain is not.
- Voice — Phase 5.
- Browser, screen, and coding tools — Phase 6.
- Calendar, email, and messaging — Phase 7.
- Android/remote access — Phase 8.
- Advanced hardening and packaging — Phase 9.
- Plugins, hardware, and IoT — Phase 10.

## Prerequisites

- Windows 10/11
- Python 3.12
- Git

Node.js is required to run or build the browser UI. Rust and the Tauri CLI are required only for the native desktop window, which is not ready yet.

## Setup

From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and fill in only the values you need. The real `.env` file is local and must never be committed.

## Run

```powershell
.\.venv\Scripts\python.exe -m jarvis
```

The server binds to the validated loopback address and port from `.env`. Do not expose it publicly.

### Desktop interface

In a second terminal:

```powershell
Set-Location "E:\Programming\OKAY FINAL AI I MAKE\desktop"
npm run dev
```

Open `http://localhost:1420`. The UI calls the backend at `http://127.0.0.1:8765` and requires the backend to be running. The browser UI is verified; the native Tauri window is blocked by the local Windows toolchain.

The UI uses real token counts returned by the provider. Because Gemini API keys do not expose a live quota endpoint, the meter tracks usage against a local daily budget (`LOCAL_DAILY_TOKEN_BUDGET`, default 1,000,000) and stores it in `var/usage.db`.

## Model providers

### Gemini primary

Add a Gemini API key to `.env`:

```dotenv
DEFAULT_MODEL_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3-flash-preview
LOCAL_FALLBACK_ENABLED=true
```

The key is sent through the `x-goog-api-key` header and is not included in logs or API responses.

### Ollama fallback or primary

Start Ollama and make sure the configured model is installed:

```powershell
ollama serve
ollama pull llama3.1
```

Relevant settings:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.1
```

When Gemini is primary and `LOCAL_FALLBACK_ENABLED=true`, a Gemini failure falls back to Ollama. When Ollama is selected as the active provider, it is used directly.

### Runtime provider selection

Inspect provider status:

```powershell
Invoke-RestMethod http://127.0.0.1:<API_PORT>/models
```

Switch the active provider for the running process:

```powershell
Invoke-RestMethod `
  -Method Put `
  -Uri "http://127.0.0.1:<API_PORT>/models/active" `
  -ContentType "application/json" `
  -Body '{"provider": "ollama"}'
```

Runtime selection is in-memory and resets to `DEFAULT_MODEL_PROVIDER` when the backend restarts.

If no provider is available, `POST /chat` returns `503`. It does not fabricate an answer.

## Chat

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:<API_PORT>/chat" `
  -ContentType "application/json" `
  -Body '{"message": "What is my disk usage?"}'
```

The response includes:

- `reply`
- `provider` and `providers_used`
- `fallback_used`
- `tool_results`
- `execution_verified`
- `iterations`
- `conversation_id`
- `warnings`

A tool is executed only through the Phase 1 registry. The model cannot grant itself permission.

## Memory

Create a memory:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:<API_PORT>/memory" `
  -ContentType "application/json" `
  -Body '{"kind":"personal","content":"My preferred editor is VS Code.","source":"user","confidence":0.9,"project":"jarvis"}'
```

Search:

```powershell
Invoke-RestMethod "http://127.0.0.1:<API_PORT>/memory/search?q=preferred%20editor"
```

Inspect and export:

```powershell
Invoke-RestMethod http://127.0.0.1:<API_PORT>/memory
Invoke-RestMethod http://127.0.0.1:<API_PORT>/memory/export
Invoke-RestMethod http://127.0.0.1:<API_PORT>/memory/stats
Invoke-RestMethod http://127.0.0.1:<API_PORT>/memory/events
```

Correct or delete:

```powershell
Invoke-RestMethod `
  -Method Patch `
  -Uri "http://127.0.0.1:<API_PORT>/memory/<MEMORY_ID>" `
  -ContentType "application/json" `
  -Body '{"content":"My preferred editor is Neovim.","confidence":0.99}'

Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:<API_PORT>/memory/<MEMORY_ID>"
```

Memory is stored locally at `MEMORY_DB_PATH`. Retrieved memory is treated as untrusted data, not instructions.

## Verify

```powershell
Invoke-RestMethod http://127.0.0.1:<API_PORT>/health
Invoke-RestMethod http://127.0.0.1:<API_PORT>/tools
Invoke-RestMethod http://127.0.0.1:<API_PORT>/models
```

Execute a read-only tool:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:<API_PORT>/tools/get_system_info/execute" `
  -ContentType "application/json" `
  -Body "{}"
```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pip check
```

Current local result: **113 tests passed**, Ruff clean, Ruff format clean, mypy clean, `pip check` clean, and `npm run build` passes in `desktop/`.

## Configuration

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development`, `test`, or `production` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `TIMEZONE` | Valid IANA timezone, for example `UTC` |
| `API_HOST` | Loopback IP address only |
| `API_PORT` | Non-privileged TCP port |
| `AUDIT_LOG_PATH` | Local JSONL tool-audit file; defaults to `var/audit.jsonl` |
| `DEFAULT_MODEL_PROVIDER` | `gemini` or `ollama` |
| `LOCAL_FALLBACK_ENABLED` | Allow Gemini failures to fall back to Ollama |
| `OLLAMA_BASE_URL` | Loopback Ollama origin |
| `OLLAMA_MODEL` | Installed Ollama model name |
| `GEMINI_MODEL` | Gemini model name |
| `GEMINI_API_KEY` | Gemini credential; must remain local and is never logged |
| `MODEL_TIMEOUT_SECONDS` | Provider request timeout |
| `MAX_TOOL_ITERATIONS` | Maximum model/tool loop iterations |
| `MAX_TOOL_CALLS_PER_TURN` | Maximum tool calls in one chat turn |
| `MEMORY_DB_PATH` | Local SQLite memory database |
| `MEMORY_MAX_RESULTS` | Maximum retrieved memories per request |
| `MEMORY_MIN_SCORE` | Minimum retrieval score |
| `MEMORY_RETENTION_DAYS` | Retention for stale superseded records |
| `MEMORY_WORKING_TTL_HOURS` | Default working-memory lifetime |
| `MEMORY_CONTEXT_MAX_CHARS` | Maximum memory text inserted into the model prompt |
| `MEMORY_AUTO_STORE_CHAT` | Store completed chat turns as episodic memory |
| `USAGE_DB_PATH` | Local SQLite daily token ledger; defaults to `var/usage.db` |
| `LOCAL_DAILY_TOKEN_BUDGET` | Local daily token budget used by the UI meter; default `1,000,000` |

The remote-access and wake-word variables in `.env` remain reserved for later phases and are intentionally ignored.

## Tool safety model

Every tool declares:

- A unique name and description.
- A validated Pydantic input schema.
- A structured Pydantic output schema.
- A risk level: `READ`, `LOW`, `CONFIRM`, or `CRITICAL`.
- A timeout in seconds.

The registry applies a policy that auto-allows only `READ` tools. `LOW`, `CONFIRM`, and `CRITICAL` tools are denied because no confirmation channel exists yet. The registry:

1. Rejects unknown tools.
2. Checks the declared risk level before execution.
3. Validates arguments against the tool schema.
4. Enforces the declared timeout.
5. Validates the tool's output.
6. Returns a structured result instead of leaking raw exceptions.
7. Writes an audit record for every invocation.

The current tools are read-only. There is no shell execution, filesystem modification, process termination, browser automation, or remote control.

## Memory safety

- Memory is stored locally in SQLite.
- Each record has a source, confidence, timestamps, and optional project context.
- Identical active content is deduplicated.
- Keyed corrections supersede the previous active value.
- Working memory expires.
- Expired and stale superseded records are cleaned at startup.
- Hard deletion removes the content; the memory event log retains only a content-free action record.
- Retrieved memory is explicitly marked as untrusted data in the model prompt.
- The user can inspect, correct, export, and delete memory through the local API.
- Chat episode auto-storage can be disabled with `MEMORY_AUTO_STORE_CHAT=false`.

## Audit logging

Tool audit records are appended as JSON lines to `AUDIT_LOG_PATH` and include the tool name, risk level, permission decision, outcome, duration, and sanitized arguments. Sensitive-looking argument keys and long strings are redacted. Tool result payloads are not written to the audit log.

Memory mutations are recorded in the local SQLite `memory_events` table without storing deleted content. Audit files and local databases are ignored by Git.

## Security baseline

- The API binds only to a loopback address.
- Health checks work without AI credentials.
- Gemini API keys are held in `SecretStr` settings and are not logged or returned by the API.
- The model can request a tool, but the registry enforces permissions and validates inputs.
- Tool results are treated as untrusted data.
- Memory is local and bounded before insertion into model context.
- The API is currently unauthenticated but loopback-bound. Do not expose it publicly or use a public tunnel until Phase 8 authentication and authorization are implemented.
- Do not run the assistant with administrator privileges by default.

## Known current limitations

- Live Gemini chat has been verified with `gemini-3-flash-preview`. The model name may change or be retired; update `GEMINI_MODEL` if the provider reports it unavailable.
- The usage meter is a local budget ledger, not a live Google quota. Gemini API keys do not expose remaining quota through this API.
- Ollama is installed but its service currently fails to start with a Windows paging-file error; no live Ollama model has been verified.
- Runtime model selection is not persisted across restarts.
- Chat responses are not streamed.
- Memory embeddings are lightweight lexical hashing embeddings, not a deep semantic model; retrieval is brute-force over a bounded candidate set.
- Retention cleanup runs at startup rather than on a schedule.
- The browser UI is implemented and verified; the native Tauri window is not available yet because the local MSVC/Windows SDK toolchain is incomplete.
- “Listening” in the UI currently means chat-input focus/typing, not microphone capture. Voice is Phase 5.
- Voice, browser automation, integrations, and remote access do not exist yet.
- The Tauri/Rust toolchain installation failed locally with installer exit code `3221225786`; Phase 4 native launch remains blocked until the toolchain is available.

## Documentation

- `docs/phase-status.md` — implemented, tested, blocked, and pending-sign-off status.
- `docs/README.md` — product-vision draft; currently incomplete and retained for reference.
- `AGENTS.md` — project constitution and development rules.
