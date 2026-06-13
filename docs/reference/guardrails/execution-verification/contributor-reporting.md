---
aliases:
 - "Work Summary Formats"
 - "Contributor Reporting"
 - "Agent Handoff Formats"
 - "Delivery return format"
tags:
 - audience/team
 - sot/true
status: stable
owner: docs-team
audience: team
scope: Lightweight work summaries for direct-develop work.
version: v3.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Work Summary Formats

Use lightweight summaries for ordinary work. The repo no longer requires committed plan artifacts, committed lane reports, or review merge reports.

The purpose is still the same: make the result reviewable and make remaining risk visible.

## Default Final Summary

For most tasks, the final response should include:

| Field | Meaning |
| --- | --- |
| Changed surfaces | files, modules, or docs areas that changed |
| Validation | commands run and whether they passed |
| Residual risk | skipped checks, known limits, or unrelated dirty state |
| Follow-up | only concrete next work, not generic offers |

Keep the summary short unless the change is broad or risky.

## Larger Work Summary

For broad refactors, use this structure in the final response or PR body:

```markdown
## Summary
- <what changed>
- <what is now true>

## Validation
- `<command>`: <pass/fail + short detail>

## Risks
- <risk or skipped check>

## Notes
- <unrelated dirty state, migration note, or follow-up>
```

## Planning Artifacts

Do not create new committed artifacts under `Plans/`.

Use one of these instead:

- update the relevant SoT under `docs/reference/**`;
- keep ephemeral planning in the conversation;
- write a PR description when a PR exists;
- create an issue only when durable tracking is useful.

## Related

- [Codex Subagent Coordination](multi-agent-collaboration.mdx)
- [Branch & Worktree Flow](branch-and-worktree-flow.mdx)
- [Commit Standards](commit-standards.mdx)

## Agent Rule { #agent-rule }

```markdown
## Work Summary Formats
- Ordinary work does not require committed plan artifacts, committed lane reports, or review merge reports.
- Do not create new active `Plans/` artifacts.
- Use concise final summaries with:
  - changed surfaces
  - validation commands/results
  - residual risks or skipped checks
  - concrete follow-up when needed
- For broad work, use Summary / Validation / Risks / Notes in the final response or PR body.
- Long-term decisions must be promoted to `docs/reference/**`.
```
