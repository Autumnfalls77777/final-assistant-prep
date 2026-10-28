# JARVIS - Personal Desktop AI Assistant

> **Document status:** This is an incomplete product-vision draft retained for reference. Current setup, run, test, and security instructions are in the root `README.md`. Sections 7–18 of this document are not present yet.

> A modular, local-first personal AI assistant for Windows, designed to combine natural voice interaction, desktop automation, persistent memory, productivity integrations, and secure mobile control.

**Project status:** Phase 1 — Tool Registry (implementation verified; owner sign-off pending)  
**Platform:** Windows desktop, with Android companion planned  
**Development approach:** Incremental, phase-gated development  
**Primary objective:** Build a reliable, extensible personal AI assistant without sacrificing maintainability, privacy, or security.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Vision and Objectives](#2-vision-and-objectives)
3. [Planned Capabilities](#3-planned-capabilities)
4. [Technology Stack](#4-technology-stack)
5. [System Architecture](#5-system-architecture)
6. [Development Roadmap](#6-development-roadmap)
7. [Repository Structure](#7-repository-structure)
8. [Memory Architecture](#8-memory-architecture)
9. [Security Principles](#9-security-principles)
10. [Development Environment](#10-development-environment)
11. [Installation and Setup](#11-installation-and-setup)
12. [Running the Application](#12-running-the-application)
13. [Testing and Verification](#13-testing-and-verification)
14. [Environment Configuration](#14-environment-configuration)
15. [Development Workflow](#15-development-workflow)
16. [Phase Completion Protocol](#16-phase-completion-protocol)
17. [Future Extensions](#17-future-extensions)
18. [Current Status](#18-current-status)

---

## 1. Project Overview

JARVIS is a personal AI assistant that lives on the Windows desktop rather than inside a browser tab.

The application will eventually provide a floating, interactive assistant that can be summoned using a global keyboard shortcut or a voice wake word. Users will be able to communicate through text and speech, request information, execute approved computer actions, manage productivity workflows, and interact with their laptop remotely through a companion Android application.

The assistant will combine cloud-based reasoning with local AI capabilities. Gemini will provide cloud reasoning when configured, while Ollama will serve as an optional local model provider and fallback. Speech recognition and speech synthesis are intended to run locally to reduce latency and avoid unnecessary transmission of voice data.

JARVIS is being developed incrementally. Each phase must produce a working, testable result before development continues.

### Core philosophy

- Build a dependable assistant before building an elaborate interface.
- Keep every subsystem modular and independently testable.
- Prefer local processing when practical.
- Require explicit permissions for consequential actions.
- Maintain reliable, searchable, editable memory.
- Keep user-facing responses concise and relevant.
- Make failures visible instead of hiding them.
- Never claim an action succeeded without verified results.

---

## 2. Vision and Objectives

### Primary objectives

1. Create a lightweight desktop application with a persistent floating assistant.
2. Enable natural text and voice interaction.
3. Execute approved Windows operations through dedicated tools.
4. Use browser automation to complete bounded tasks.
5. Maintain structured long-term memory of user preferences and projects.
6. Integrate calendar, email, reminders, and supported messaging workflows.
7. Send useful notifications to the user's phone.
8. Support authenticated remote control of the user's own computer.
9. Provide configurable conversational, coding, research, and productivity modes.
10. Keep the architecture extensible for future agents, plugins, and hardware integrations.

### Non-goals for the initial release

The first version will not attempt to implement every capability at once.

The following are explicitly out of scope until their assigned phases:

- Unrestricted shell execution by an LLM.
- Automatic access to every personal account.
- Unauthenticated remote computer control.
- A custom screen lock presented as a replacement for Windows authentication.
- An autonomous agent with unrestricted permissions.
- Premature multi-agent orchestration.
- A complex cloud database deployment before local persistence is proven.
- Hardware or IoT control before the core architecture is stable.

---

## 3. Planned Capabilities

### 3.1 Desktop interface

The intended desktop experience includes:

- A small floating orb, initially positioned near the bottom-right corner.
- Expandable chat and command input.
- Global activation and emergency-stop shortcuts.
- Voice and typing interaction.
- System tray integration.
- Listening, thinking, executing, speaking, and error indicators.
- Settings for models, voice, memory, permissions, and integrations.

### 3.2 Windows automation

Planned capabilities include:

- Launching approved applications.
- Opening files, folders, and URLs.
- Reading selected system information.
- Monitoring CPU, memory, disk space, battery, and available GPU metrics.
- Inspecting running processes.
- Managing supported brightness and Bluetooth controls.
- Capturing screenshots and interpreting selected screen content.
- Locking or putting the computer to sleep.
- Performing explicitly authorized shutdown operations.

Hardware-dependent controls must detect unsupported devices and report meaningful errors.

### 3.3 Browser automation

Playwright will be used for controlled browser workflows, such as:

- Navigating websites.
- Searching and extracting page information.
- Interacting with forms.
- Completing bounded repetitive tasks.
- Summarizing selected web pages.
- Assisting with authenticated sessions where permitted.

Browser content is untrusted input. Instructions found inside web pages must never override JARVIS security policies.

### 3.4 Productivity integrations

Future integrations include:

- Google Calendar event creation and scheduling.
- Meeting conflict detection.
- Gmail search, summaries, and draft creation.
- Notifications for selected important messages.
- Reminders and follow-up tasks.
- Supported WhatsApp messaging workflows.

External communications and consequential changes must use appropriate permissions and confirmation rules.

### 3.5 Remote companion

The planned Android companion will support:

- Text and voice interaction.
- Laptop connectivity status.
- Battery and resource alerts.
- Push notifications.
- Authenticated remote commands.
- Lock, sleep, and other approved computer operations.
- Device pairing and revocation.

The desktop service must authenticate and authorize remote requests independently of the mobile interface.

---

## 4. Technology Stack

| Component | Planned technology |
|---|---|
| Desktop framework | Tauri 2 |
| Frontend | React, TypeScript, Vite |
| Desktop-native layer | Rust through Tauri |
| Backend | Python |
| Backend API | FastAPI |
| Data validation | Pydantic |
| ASGI server | Uvicorn |
| AI orchestration | LangChain |
| Stateful workflows | LangGraph when justified |
| Cloud reasoning | Gemini API |
| Local LLM | Ollama |
| Speech recognition | Faster-Whisper or another suitable local STT engine |
| Speech synthesis | Kokoro or Piper |
| Wake-word detection | A suitable local wake-word engine |
| Structured persistence | SQLite |
| Semantic memory | Local embeddings and a replaceable vector index |
| Browser automation | Playwright |
| Mobile application | React Native with Expo |
| Testing | pytest, frontend tests, integration tests |
| Version control | Git and GitHub |

Dependencies will be selected and pinned as appropriate during their respective phases. This table defines the intended direction, not a requirement to install every library during initial setup.

### Architecture decisions

- Python is the primary AI and automation backend.
- React is responsible for the desktop interface.
- Tauri provides the native desktop container and selected native capabilities.
- The backend and desktop UI communicate through an explicit interface.
- Gemini and Ollama are accessed through provider adapters.
- Voice processing is independent of the LLM provider.
- Local storage is the default for personal memory.
- Mobile support is introduced after the desktop service and authentication design are stable.

---

## 5. System Architecture

The high-level architecture is:

```text
                    USER
                     |
          +----------+-----------+
          |                      |
      DESKTOP UI             ANDROID APP
   Tauri + React             (Phase 8)
          |                      |
          +----------+-----------+
                     |
              AUTHENTICATED API
                     |
              JARVIS BACKEND
                 FastAPI
                     |
            AGENT ORCHESTRATOR
                     |
          +----------+-----------+
          |          |           |
       AI MODELS   MEMORY    POLICY ENGINE
          |          |           |
      Gemini /    SQLite +     TOOL REGISTRY
      Ollama      Vector DB        |
                             +------+-------+
                             |      |       |
                          Windows Browser Integrations
                          Tools    Tools     Tools
```

### Architectural boundaries

**Frontend:** Handles presentation, user interaction, UI state, and status display.

**Backend:** Owns request processing, configuration, model integration, memory, tool execution, and policy enforcement.

**Agent orchestrator:** Interprets requests, retrieves relevant context, selects tools, and coordinates results.

**Tool registry:** Exposes explicitly defined, validated operations.

**Policy engine:** Enforces authorization, risk classification, confirmation requirements, and execution restrictions.

**Memory subsystem:** Stores and retrieves structured facts and relevant historical information.

**Voice subsystem:** Handles wake-word detection, speech recognition, speech synthesis, and interruption.

**Integration layer:** Contains external provider adapters for calendar, email, messaging, and other services.

No single module should be responsible for the entire assistant.

---

## 6. Development Roadmap

Each phase is a separate milestone. A phase is not complete merely because code has been generated or the application starts.

### Phase 0 — Foundation

- Establish repository structure.
- Create and validate development configuration.
- Initialize the Python backend.
- Add basic health checks and tests.
- Document setup instructions.
- Establish logging, error handling, and development conventions.

**Acceptance criteria:** The backend starts, configuration is validated, the health endpoint responds, and initial tests pass without requiring API credentials.

### Phase 1 — Tool registry and Windows automation

- Define tool interfaces and schemas.
- Add permissions and risk categories.
- Implement independently testable Windows tools.
- Add timeouts and error handling.
- Add audit logging.

**Acceptance criteria:** Initial tools work independently, reject invalid inputs, and enforce their declared permissions.

### Phase 2 — AI orchestration

- Integrate Gemini.
- Integrate Ollama.
- Implement model routing and fallback behavior.
- Add structured tool calling.
- Add concise response formatting.
- Validate execution results before reporting success.

**Acceptance criteria:** The assistant can interpret a request, choose an approved tool, execute it, and return a truthful result.

### Phase 3 — Persistent memory

- Add structured memory records.
- Implement personal, project, episodic, working, and semantic memory.
- Add local embeddings and vector retrieval.
- Implement deduplication, correction, and retention.
- Add memory inspection and deletion.

**Acceptance criteria:** Relevant information persists across restarts and is retrieved accurately without flooding the model context.

### Phase 4 — Desktop interface

- Implement the Tauri and React application.
- Create the floating orb and expandable chat.
- Add global activation shortcuts.
- Integrate backend communication.
- Display application state and errors.

**Acceptance criteria:** The assistant can be summoned from other applications and communicates reliably with the backend.

### Phase 5 — Voice and modes

- Add local wake-word detection.
- Add local speech recognition and synthesis.
- Implement speech interruption and cancellation.
- Add conversational, coding, research, and productivity modes.

**Acceptance criteria:** Voice interaction works reliably without blocking the UI, and speech can be interrupted.

### Phase 6 — Browser, screen, and coding tools

- Integrate Playwright.
- Add controlled screen capture and OCR or vision processing.
- Implement workspace-scoped coding assistance.
- Add safe file operations and test execution.

**Acceptance criteria:** Bounded tasks complete successfully with observable results and controlled permissions.

### Phase 7 — Calendar, email, and messaging

- Implement supported Google Calendar integration.
- Implement Gmail OAuth and message workflows.
- Add reminders and notification rules.
- Investigate supported WhatsApp integration options.

**Acceptance criteria:** Authorized account operations work, permissions are scoped appropriately, and consequential actions follow confirmation rules.

### Phase 8 — Android companion and remote control

- Build the React Native companion.
- Implement secure device pairing.
- Add authenticated remote communication.
- Implement notifications and laptop status.
- Add approved remote actions.

**Acceptance criteria:** A paired device can communicate securely with the running desktop service, and revoked devices lose access.

### Phase 9 — Security and reliability

- Add recovery and process supervision.
- Improve auditability and diagnostic reporting.
- Test authentication and authorization.
- Validate cancellation, crash handling, and safe