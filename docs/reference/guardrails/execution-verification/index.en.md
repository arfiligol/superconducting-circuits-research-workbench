---
aliases:
  - Execution & Verification
  - Verification Rules
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/execution
status: stable
owner: docs-team
audience: contributor
scope: Index for build, lint, test, and CI rules.
version: v2.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Execution & Verification

This section defines the verification baseline for the rewrite branch.
If the current scripts lag behind the target rules, that is a migration task, not a reason to drop the rules.

- [Build Commands](./build-commands.en.md)
- [Linting & Formatting](./linting.en.md)
- [Testing](./testing.en.md)
- [CI Gates](./ci-gates.en.md)
- [Commit Standards](./commit-standards.en.md)

## Agent Rule { #agent-rule }

```markdown
## Execution & Verification
- This section defines the workspace baseline for build, lint, type-check, test, and CI.
- When changing code, run the checks that are directly relevant to the touched area first.
- The rewrite-branch target baseline spans app/frontend, app/backend, Julia Runner, desktop, and docs.
```
