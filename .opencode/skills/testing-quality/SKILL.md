---
name: testing-quality
description: Plan and execute focused tests, debug failures, prevent regressions, and verify implementation claims in the JARVIS project.
---

# Testing and Quality Rules

1. Inspect the existing code, dependencies, and test conventions before changing anything.
2. Write or update tests for the behavior being implemented, including relevant edge cases.
3. Prefer deterministic unit tests; isolate network calls, external services, and hardware-dependent behavior.
4. Test invalid input, missing configuration, exceptions, timeouts, and permission-denied cases where relevant.
5. Run focused tests first, then the appropriate broader test suite.
6. Never claim tests passed unless the commands actually ran and their results support that claim.
7. Distinguish tests that passed, failed, were skipped, or could not run.
8. Do not hide failures, weaken assertions, or delete tests just to obtain a green result.
9. Fix regressions introduced by current-phase changes before reporting completion.
10. Keep changes within the authorized phase and document any remaining limitations.
11. Never mark the project owner as having verified a phase. Only the owner can approve it.
