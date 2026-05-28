---
aliases:
  - "Task Scope Sizing"
  - "Prompt Grading"
  - "Prompt 分級"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/execution
status: stable
owner: docs-team
audience: team
scope: Task sizing and verification expectations for direct Codex execution and optional subagent use.
version: v2.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Task Scope Sizing

Use task levels to choose how much context, verification, and reporting a change needs. These levels are guidance for the current Codex conversation, not a mandatory multi-agent dispatch system.

## Scope Levels

| Level | Use for | Expected verification |
| --- | --- | --- |
| `L1 Fixup` | one bug, wording issue, contract mismatch, or failing check | closest targeted check |
| `L2 Slice` | one coherent workflow or surface slice | touched-area unit/integration check |
| `L3 Milestone` | several related slices in one workstream | broader regression checks for that workstream |
| `L4 System Push` | broad system-level contract change | cross-surface verification |

Choose the smallest level that completes a meaningful delivery.

## Fast Iteration Rule

Direct implementation is acceptable when the request is clear and the SoT is already known. Do not pause just to produce a formal plan.

Write a short plan only when it reduces risk:

- broad refactor;
- ambiguous scope;
- high-risk data/security/runtime change;
- multiple surfaces that need sequencing;
- user explicitly asks for a plan.

## Prompt Fields When Needed

When a task needs explicit scoping, use these fields in the conversation or PR body:

- Goal
- Current state
- Touched area
- Non-goals
- Verification
- Risks / open decisions

Dedicated branch/worktree, `Allowed Area`, `Do Not Touch`, and subagent work lane assignments are optional tools. They are not required fields for ordinary work.

## Review Rule

Review the result against:

- current SoT;
- actual code/docs behavior;
- touched-area validation;
- user-visible behavior when applicable.

Do not judge success by whether an internal prompt structure was followed exactly.

## Related

- [Codex Subagent Coordination](./multi-agent-collaboration.md)
- [Branch & Worktree Flow](./branch-and-worktree-flow.md)
- [Testing](./testing.md)

## Agent Rule { #agent-rule }

```markdown
## Task Scope Sizing
- Use L1/L2/L3/L4 as lightweight task-size guidance, not mandatory dispatch ceremony.
- Choose the smallest level that completes a meaningful delivery.
- Direct implementation is allowed when the request is clear and SoT is known.
- Write a short plan only when it reduces risk or the user asks for one.
- Dedicated branches/worktrees, `Allowed Area`, `Do Not Touch`, and subagent work lane assignments are optional tools.
- Review outcomes against SoT, actual behavior, and validation results rather than prompt literalism.
- For user-visible frontend changes, include browser-based verification with screenshot or equivalent visual evidence when practical.
```
