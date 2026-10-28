# JARVIS

A modular, local-first personal AI assistant for Windows.

**Current implementation:** Phase 0 foundation and Phase 1 read-only tool registry.  
**Owner sign-off:** Pending. Both phases were authorized; local implementation verification is complete.

## Current scope

The backend currently provides:

- Validated configuration loaded from the project `.env`.
- A loopback-only FastAPI service.
- `GET /health` liveness checks.
- A typed tool registry with permission checks, timeouts, structured errors, and JSONL audit logging.
- Four read-only Windows system tools:
  - `get_system_info`
  - `get_disk_usage`
  - `list_processes`
  - `get_battery_status`
- Tool discovery through `GET /tools`.
- Explicit tool execution through `POST /tools/{tool_name}/execute`.

The following are intentionally **not** implemented yet:

- AI/model orchestration — Phase 2.
- Memory — Phase 3.
- Desktop UI — Phase 4.
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

Node.js is only needed later for the desktop/mobile phases. Rust/Tauri is only needed for Phase 4.

## Setup

From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

The real `.env` file is local and must never be committed. Use `.env.example` as the template.

## Run

```powershell
.\.venv\Scripts\python.exe -m jarvis
```

The server binds to the validated loopback address and port from `.env`. Do not expose it publicly.

## Verify

```powershell
Invoke-RestMethod http://127.0.0.1:<API_PORT>/health
Invoke-RestMethod http://127.0.0.1:<API_PORT>/tools
```

Execute a read-only tool:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:<API_PORT>/tools/get_system_info/execute" `
  -ContentType "application/json" `
  -Body "{}"
```

Useful bounded process query:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:<API_PORT>/tools/list_processes/execute" `
  -ContentType "application/json" `
  -Body '{"limit": 5, "sort_by": "memory"}'
```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pip check
```

## Configuration

Phase 0/1 reads only:

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development`, `test`, or `production` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `TIMEZONE` | Valid IANA timezone, for example `UTC` |
| `API_HOST` | Loopback IP address only |
| `API_PORT` | Non-privileged TCP port |
| `AUDIT_LOG_PATH` | Local JSONL audit file; defaults to `var/audit.jsonl` |

The model, remote-access, and wake-word variables in `.env` are reserved for later phases and are intentionally ignored until those phases are authorized.

## Tool safety model

Every tool declares:

- A unique name and description.
- A validated Pydantic input schema.
- A structured Pydantic output schema.
- A risk level: `READ`, `LOW`, `CONFIRM`, or `CRITICAL`.
- A timeout in seconds.

The registry applies a Phase 1 policy that auto-allows only `READ` tools. `LOW`, `CONFIRM`, and `CRITICAL` tools are denied because no confirmation channel exists yet. The registry:

1. Rejects unknown tools.
2. Checks the declared risk level before execution.
3. Validates arguments against the tool schema.
4. Enforces the declared timeout.
5. Validates the tool's output.
6. Returns a structured result instead of leaking raw exceptions.
7. Writes an audit record for every invocation.

The Phase 1 tools are read-only. There is no shell execution, filesystem modification, process termination, browser automation, or remote control.

## Audit logging

Audit records are appended as JSON lines to `AUDIT_LOG_PATH` and include the tool name, risk level, permission decision, outcome, duration, and sanitized arguments. Sensitive-looking argument keys and long strings are redacted. Tool result payloads are not written to the audit log.

The audit file is local and ignored by Git. It is not a substitute for operating-system auditing, and audit records are written after the invocation rather than before it.

## Security baseline

- The API binds only to a loopback address.
- No API keys are required.
- No shell, filesystem, process-control, or browser automation is exposed.
- Only read-only tools are enabled.
- Tool permissions and audit logging are enforced in Phase 1.
- The `.env` file is ignored by Git.
- Do not use a public tunnel or expose the backend until the remote-access phase is approved and authentication is implemented.

## Documentation

- `docs/phase-status.md` — implemented, tested, and known-limitation status.
- `docs/README.md` — product vision draft; currently incomplete and retained for reference.
- `AGENTS.md` — project constitution and development rules.
