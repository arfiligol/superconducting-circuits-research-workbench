---
aliases:
  - "Codex Subagent Coordination"
  - "Multiple Agent Collaboration"
  - "Agent Collaboration Framework"
  - "多 Agent 協作"
tags:
  - audience/team
  - sot/true
status: stable
owner: docs-team
audience: team
scope: Codex-managed subagent coordination, single-owner delivery, and verification expectations without repo-mandated agent families.
version: v3.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Codex Subagent Coordination

Codex can now open and coordinate subagents itself. The repo no longer requires humans or prompts to split work into the old fixed role taxonomy.

Treat subagents as an execution detail. The current conversation owns the final diff, verification, and report.

!!! important "Single visible owner"
    Even if Codex uses subagents internally, the delivered change should read as one coherent update. The final response must identify what changed, what was verified, and what remains risky or unverified.

## Current Policy

| Concern | Current rule |
| --- | --- |
| Subagent use | optional, chosen by Codex when useful |
| Manual agent lane split | not required |
| `Plans/` coordination files | retired; do not create new active plan artifacts |
| Direct `develop` work | allowed when the working tree stays coherent and touched-area checks are run |
| Final accountability | current conversation owns the integrated result |

## Coordination Rules

- Load the relevant SoT before changing code or docs.
- Use subagents only when they reduce real coordination cost.
- Do not require a separate planning pass before implementation.
- Do not require a separate testing pass before verification.
- Do not create persistent prompt bundles in `Plans/`.
- Keep final verification proportional to the touched area.
- For user-visible frontend changes, use a real browser smoke and screenshot or equivalent visual evidence.

## When To Use Subagents

Subagents are useful when:

- a change has independent docs, backend, frontend, runner, or test areas;
- a large review benefits from parallel inspection;
- a migration requires comparing several surfaces at once;
- the user explicitly asks Codex to parallelize.

They are not required for small fixes, docs cleanup, or direct SoT edits.

## Handoff

Prefer concise in-thread summaries over committed planning files:

- changed files or surfaces;
- validation commands and results;
- known risks or skipped checks;
- remaining follow-up if it is concrete.

Long-term decisions belong in `docs/reference/**`, not in temporary planning artifacts.

## Related

- [Branch & Worktree Flow](./branch-and-worktree-flow.md)
- [Task Scope Sizing](./prompt-grading.md)
- [Work Summary Formats](./contributor-reporting.md)
- [Testing](./testing.md)

## Agent Rule { #agent-rule }

```markdown
## Codex Subagent Coordination
- Codex may open and coordinate subagents internally when useful.
- The repo no longer requires the old fixed role taxonomy.
- Do not require a separate planning pass, testing pass, or prewritten prompt bundle before implementation.
- Do not create new active `Plans/` coordination artifacts.
- The current conversation owns the final integrated diff, verification, and report.
- Direct `develop` updates are allowed when the working tree stays coherent and touched-area checks are run.
- Long-term decisions belong in `docs/reference/**`, not temporary planning files.
- Final reports should summarize changed surfaces, validation, risks, and any skipped checks.
```
