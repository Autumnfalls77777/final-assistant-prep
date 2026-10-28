# JARVIS Phase Status

## Current Phase

Phase 1 — Tool Registry and Windows Automation

**Implementation status:** Phase 0 and Phase 1 are implemented and locally verified.  
**Authorization:** Both phases were authorized by the owner.  
**Owner sign-off:** Pending. This file does not mark either phase as owner-verified.

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

### Phase 0 verification

- Initial Phase 0 test run: **18 passed**.
- Live server check: `GET /health` returned `200` with `status=ok`.
- Default `.env` configuration also started successfully and served `/health` and `/tools` on loopback.
- Listener check: `127.0.0.1` only.
- Invalid configuration check: `API_HOST=0.0.0.0` exited nonzero and was rejected by validation.
- `.env` is ignored by Git; `.env.example` is not ignored.

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
- [x] Tests for success, invalid input, unknown tools, permission denial, timeouts, execution failures, invalid tool output, audit redaction, and API error mapping.

### Phase 1 verification

Final automated checks:

```text
pytest -q                        44 passed
ruff check .                     All checks passed
ruff format --check .            38 files already formatted
mypy                             Success: no issues found in 21 source files
pip check                        No broken requirements found
```

Live local server verification:

```text
GET  /health                              200, status=ok
GET  /tools                               200, 4 read-only tools
POST /tools/get_system_info/execute       200, ok=true
POST /tools/list_processes/execute        200, ok=true, 3 processes returned
POST /tools/get_disk_usage/execute        200, ok=true
POST /tools/get_battery_status/execute    200, ok=true
POST /tools/list_processes/execute        invalid limit -> 422
POST /tools/missing/execute               unknown tool -> 404
Listener                                  127.0.0.1 only
Audit records written                     6
```

The live server was started on a deliberately chosen local verification port, queried through loopback, and stopped. It was not exposed publicly.

### Manual verification instructions

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m jarvis
```

In another terminal, using the configured local port:

```powershell
Invoke-RestMethod http://127.0.0.1:<API_PORT>/health
Invoke-RestMethod http://127.0.0.1:<API_PORT>/tools
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:<API_PORT>/tools/get_system_info/execute" -ContentType "application/json" -Body "{}"
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:<API_PORT>/tools/list_processes/execute" -ContentType "application/json" -Body '{"limit": 5, "sort_by": "memory"}'
```

Check the audit file:

```powershell
Get-Content var\audit.jsonl -Tail 5
```

Stop the server with `Ctrl+C`. Confirm it is loopback-bound:

```powershell
Get-NetTCPConnection -State Listen |
  Where-Object LocalPort -eq <API_PORT> |
  Select-Object LocalAddress, LocalPort
```

Expected result: `127.0.0.1`.

Do not use a public tunnel or expose the backend until the remote-access phase is approved and authentication is implemented.

---

## Changed Files

### Phase 0

- `.gitignore`
- `.env.example`
- `pyproject.toml`
- `README.md`
- `backend/src/jarvis/__init__.py`
- `backend/src/jarvis/config.py`
- `backend/src/jarvis/logging.py`
- `backend/src/jarvis/main.py`
- `backend/src/jarvis/__main__.py`
- `backend/src/jarvis/api/__init__.py`
- `backend/src/jarvis/api/health.py`
- `backend/tests/conftest.py`
- `backend/tests/test_config.py`
- `backend/tests/test_health.py`
- `backend/tests/test_logging.py`
- `backend/tests/test_main.py`

### Phase 1

- `backend/src/jarvis/api/tools.py`
- `backend/src/jarvis/tools/__init__.py`
- `backend/src/jarvis/tools/base.py`
- `backend/src/jarvis/tools/policy.py`
- `backend/src/jarvis/tools/errors.py`
- `backend/src/jarvis/tools/models.py`
- `backend/src/jarvis/tools/audit.py`
- `backend/src/jarvis/tools/registry.py`
- `backend/src/jarvis/tools/builtin.py`
- `backend/src/jarvis/tools/windows/__init__.py`
- `backend/src/jarvis/tools/windows/system_info.py`
- `backend/src/jarvis/tools/windows/disk_usage.py`
- `backend/src/jarvis/tools/windows/processes.py`
- `backend/src/jarvis/tools/windows/battery.py`
- `backend/tests/test_registry.py`
- `backend/tests/test_builtin_tools.py`
- `backend/tests/test_tools_api.py`
- `README.md` updated with Phase 1 usage and safety details.

### Documentation

- `docs/README.md` — added a status banner only; the incomplete body was preserved.
- `docs/phase-status.md` — this file.

### Unchanged

- `AGENTS.md`
- `.env`
- `opencode.json`
- All five `.opencode/skills/*/SKILL.md` files
- Git history (no commits were created)

---

## Known Issues and Limitations

1. **Owner sign-off is pending** for both Phase 0 and Phase 1; both phases were authorized.
2. Only read-only tools are enabled. `LOW`, `CONFIRM`, and `CRITICAL` tools are denied because no confirmation channel exists yet.
3. The local API is unauthenticated but loopback-bound. Remote authentication and authorization are deferred to Phase 8.
4. Timeouts bound the asynchronous wait. A blocking worker thread may continue briefly after the timeout response.
5. Audit records are written after invocation, not before it. A process crash during a tool call could leave no completed audit record. No audit-log rotation is implemented.
6. Audit redaction is key-based and best-effort. Tools must not accept secrets in generic, non-sensitive-looking fields.
7. `docs/README.md` remains an incomplete product-vision draft; the root `README.md` is authoritative.
8. No AI/model orchestration, memory, desktop UI, voice, browser automation, integrations, or remote access exists yet.
9. Rust/Tauri tooling is not installed; it is deferred to Phase 4.
10. Ollama is installed but not running; it is deferred to Phase 2.
11. The global Python environment has unrelated dependency conflicts. The project uses `.venv`; global packages are not project dependencies.
12. No Git commit or remote has been created. Version-control actions require owner authorization.

---

## Next Task

Owner review and verification of Phase 0 and Phase 1.

Do **not** begin Phase 2 — AI orchestration and model integration — until the owner explicitly authorizes it.

## Owner Approval

- Phase 0: **Authorized; local verification complete; owner sign-off pending.**
- Phase 1: **Authorized; local verification complete; owner sign-off pending.**
