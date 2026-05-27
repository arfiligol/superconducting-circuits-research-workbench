---
aliases:
  - Code Quality
  - Engineering Quality
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/code-quality
status: stable
owner: docs-team
audience: contributor
scope: Index for code quality, typing, architecture boundaries, and scripts rules.
version: v2.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Code Quality

This section defines the code-quality rules for the rewrite branch.
The goal is not framework cleverness; it is stable co-evolution across UI, API, Notebook, Julia Runner, and the scientific core.

- [Code Style](./code-style.en.md)
- [Type Checking](./type-checking.en.md)
- [Design Patterns](./design-patterns.en.md)
- [Script Authoring](./script-authoring.en.md)
- [Data Handling](./data-handling.en.md)
- [Logging](./logging.en.md)

## Agent Rule { #agent-rule }

```markdown
## Code Quality
- Follow Clean Code: clear naming, small functions, single responsibility.
- UI, API, Notebook, Runner, and scripts must not each duplicate business workflows; shared rules belong in app backend services, Julia Core, Julia Runner, or explicit contract packages.
- Prefer fixing the code over adding exceptions or suppressions.
- Load sub-rules as needed: Code Style / Type Checking / Design Patterns / Script Authoring / Data Handling / Logging.
```
