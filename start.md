# JARVIS — Start Guide

PowerShell commands. Run from the project root unless stated otherwise.

```text
E:\Programming\OKAY FINAL AI I MAKE
```

The backend automatically reads the root `.env` file.  
No `GEMINI_MODEL` environment variable is needed.

---

## 1. Start the backend

Open Terminal 1:

```powershell
Set-Location "E:\Programming\OKAY FINAL AI I MAKE"
Remove-Item Env:GEMINI_MODEL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m jarvis
```

Leave this terminal running.

The backend runs at:

```text
http://127.0.0.1:8765
```

---

## 2. Start the desktop interface

Open Terminal 2:

```powershell
Set-Location "E:\Programming\OKAY FINAL AI I MAKE\desktop"
npm run dev
```

Open in a browser:

```text
http://localhost:1420
```

The UI is connected to the live backend:

- The orb shows idle, listening, thinking, and speaking states.
- Chat messages are sent to `POST /chat`.
- Gemini replies are rendered live.
- Token usage comes from the provider response.
- The usage meter refreshes from `GET /usage`.

Start the backend first. If it is offline, the UI reports the link as offline and offers a reconnect action.

---

## 3. Verify the backend

Open Terminal 3:

```powershell
Invoke-RestMethod "http://127.0.0.1:8765/health"
Invoke-RestMethod "http://127.0.0.1:8765/models"
Invoke-RestMethod "http://127.0.0.1:8765/usage"
```

Gemini should show:

```text
active_provider: gemini
model: gemini-3-flash-preview
configured: True
available: True
```

---

## 4. Verify live chat

The simplest check is to type a message in the browser UI and confirm:

1. The link indicator says `LINK ONLINE`.
2. The orb changes to `Thinking` and then `Speaking`.
3. The Gemini reply appears in the conversation.
4. The assistant message shows a token count.
5. The top-right usage meter updates.

The same path can be checked from the API:

```powershell
$body = @{ message = "Reply with exactly: JARVIS ONLINE" } | ConvertTo-Json

$response = Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8765/chat" `
  -ContentType "application/json" `
  -Body $body `
  -TimeoutSec 180

$response.provider
$response.reply
$response.usage
```

Expected:

```text
provider: gemini
reply: JARVIS ONLINE
usage: prompt_tokens, completion_tokens, total_tokens
```

---

## 5. Token usage and local budget

The usage meter is a **local daily ledger**, not a Google account quota.

Gemini API keys do not expose a live “remaining quota” endpoint. JARVIS therefore:

- Records prompt, completion, and total tokens returned by the provider.
- Stores the daily ledger in `var/usage.db`.
- Compares the total against `LOCAL_DAILY_TOKEN_BUDGET`.
- Shows tokens used, tokens left, and the percentage remaining.

Default budget:

```text
1,000,000 tokens per local day
```

The value can be changed in `.env`:

```dotenv
LOCAL_DAILY_TOKEN_BUDGET=1000000
```

Restart the backend after changing it. The ledger survives backend restarts. To intentionally reset the local usage history, stop the backend and remove `var/usage.db`.

---

## 6. Stop JARVIS

In each terminal:

```text
Ctrl + C
```

---

## First-time setup

Only needed on a new machine or after deleting the environments.

Backend:

```powershell
Set-Location "E:\Programming\OKAY FINAL AI I MAKE"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Desktop:

```powershell
Set-Location "E:\Programming\OKAY FINAL AI I MAKE\desktop"
npm install
```

---

## Backend checks

```powershell
Set-Location "E:\Programming\OKAY FINAL AI I MAKE"

.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pip check
```

Desktop build:

```powershell
Set-Location "E:\Programming\OKAY FINAL AI I MAKE\desktop"
npm run build
```

---

## Current limitation: real Tauri window

The browser UI is verified.

The real Tauri desktop window is **not ready yet**:

- Visual Studio C++ Build Tools/MSVC are missing.
- `C:` is nearly full.
- The Windows paging file is on `C:`.
- The Rust linker fails at the `dlltool` step.

Do not use this until the toolchain is fixed:

```powershell
Set-Location "E:\Programming\OKAY FINAL AI I MAKE\desktop"
npm run tauri dev
```

---

## Quick troubleshooting

If `/chat` returns an error, check the backend and configuration:

```powershell
Remove-Item Env:GEMINI_MODEL -ErrorAction SilentlyContinue
Set-Location "E:\Programming\OKAY FINAL AI I MAKE"
Select-String -Path .env -Pattern '^GEMINI_MODEL=|^API_PORT='
if (Select-String -Path .env -Pattern '^GEMINI_API_KEY=.+') {
  "GEMINI_API_KEY is set"
} else {
  "GEMINI_API_KEY is missing"
}
```

Confirm `.env` contains:

```dotenv
GEMINI_MODEL=gemini-3-flash-preview
API_PORT=8765
```

If the browser UI shows `LINK OFFLINE`:

1. Confirm the backend is running on `http://127.0.0.1:8765`.
2. Confirm the UI is open on `http://localhost:1420`.
3. Use the UI’s `Reconnect` action.
4. Check the backend terminal for errors.

If the orb is moving slowly, close extra browser tabs or other GPU-heavy windows. The UI intentionally uses transform/opacity-only animation and no large backdrop blur.

Never commit `.env` or share the API key.
