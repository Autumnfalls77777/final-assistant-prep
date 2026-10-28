---
name: phase-gated-development
description: Enforce JARVIS phase boundaries, testing, progress logging, and owner approval before starting another phase.
---

# JARVIS Phase-Gated Development

1. Read AGENTS.md, README.md, and docs/phase-status.md before making changes.
2. Identify the current phase from the status log and inspect the repository.
3. Work only on the currently authorized phase.
4. Before substantial changes, explain the plan and scope.
5. Make small, reviewable changes and preserve existing work.
6. Run relevant tests and report actual results.
7. Update docs/phase-status.md with changed files, commands, test results, limitations, and manual test instructions.
8. Never claim the owner has verified a phase.
9. When a phase is ready, report what is done and STOP.
10. Wait for explicit owner approval before starting another phase.
11. If the owner finds a bug, fix it within the current phase and record the resolution.
12. Do not implement future-phase features just because they appear in the roadmap.
