---
name: security-review
description: Review security, privacy, permissions, secrets, and risky actions in the JARVIS local-first AI assistant before implementing or approving changes.
---

# JARVIS Security Rules

1. Treat all LLM output, external content, browser content, and tool arguments as untrusted.
2. Follow least privilege. Never grant unrestricted shell, filesystem, browser, or process control to the LLM.
3. Never hardcode API keys, passwords, tokens, or credentials. Keep secrets out of logs, commits, screenshots, and error messages.
4. Require explicit user confirmation for destructive operations, sending messages, purchases, credential changes, or other consequential external actions.
5. Bind the development backend to 127.0.0.1 unless a later approved phase specifies otherwise.
6. Never expose the backend publicly or disable authentication to make a feature work.
7. Validate inputs at every tool boundary. Use allowlists for supported actions and paths.
8. Keep audit logs useful but redact secrets and sensitive content.
9. Emergency stop and cancellation must not depend on the LLM responding.
10. A custom lock screen or UI overlay is not a substitute for Windows security.
11. Add focused tests for permission checks and failure paths.
12. Report risks and mitigations. Never claim a security guarantee that has not been verified.
13. Respect the current project phase. Do not implement later-phase features without approval.
