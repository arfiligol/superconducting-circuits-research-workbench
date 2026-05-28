---
aliases:
  - "Codex Subagent Coordination"
  - "Subagent Work Lanes"
  - "多 Agent 協作"
tags:
  - audience/team
  - sot/true
status: stable
owner: docs-team
audience: team
scope: Codex-managed subagent work lanes, main-thread ownership, integrated delivery, and verification expectations.
version: v4.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Codex Subagent Coordination

Codex may open and coordinate subagents internally. Treat subagents as optional work lanes under one main thread, not as permanent project teams or fixed agent identities.

The main thread owns integration, final architecture consistency, validation, and the final report.

!!! important "Single visible owner"
    Even if Codex uses multiple subagents, the delivered change must read as one coherent update. The final response must identify what changed, what was verified, and what remains risky or unverified.

## Current Policy

| Concern | Rule |
| --- | --- |
| Main thread | owns goal, SoT loading, lane selection, integration, conflict resolution, validation, and final report |
| Subagent work lanes | optional delegation scopes chosen by Codex when they reduce real coordination cost |
| Fixed agent families | not required; do not document work as named permanent agent roles |
| `Plans/` coordination files | retired; do not create new active plan artifacts |
| Direct `develop` work | allowed when the working tree stays coherent and touched-area checks are run |
| Final accountability | current conversation owns the integrated result |

## Main Thread Responsibilities

The main thread must:

- read the relevant SoT before assigning or doing work;
- define the current vertical slice and success criteria;
- choose whether subagent work lanes are useful;
- keep subagents inside folder structure and owner-boundary rules;
- reconcile cross-lane conflicts;
- run or account for touched-area validation;
- produce the final integrated report.

## Subagent Work Lanes

Use these lanes as optional delegation scopes. They describe where a subagent may focus; they are not permanent ownership teams.

| Lane | Typical surfaces | Responsibilities |
| --- | --- | --- |
| Julia Core + Pluto Research | `core/julia/SuperconductingCircuitsCore/`, `notebooks/pluto/` | Julia Core APIs, Pluto direct research workflow, JosephsonCircuits.jl validation, component/circuit prototypes, research sweep and analysis prototypes |
| Product Async Contracts | `docs/reference/architecture/`, `core/python/sc_data_contracts/`, Backend API contracts | simulation request contracts, runner task envelopes, runner result manifest, result-view API, OpenAPI alignment |
| Backend + Runner Integration | `app/backend/`, `core/julia/SuperconductingCircuitsRunner/`, `data/staging/`, `data/trace_store/` | task lifecycle, runner claim/heartbeat/progress/cancellation/complete/fail, task dispatch, Zarr staging, manifest validation, Backend publication |
| Application Workbench | `app/frontend/`, `app/desktop/` | Simulation Workbench UI, task submission UI, task status/result viewer, Raw Data Browser integration, Electron runtime shell |
| Python Notebook / Data Inspection | `notebooks/python/`, notebook reference docs | programmable data analysis, direct local/exported/canonical data reads, Backend API use for platform state, migration/debug/emergency analysis |
| Docs / SoT Consistency | `README.md`, `docs/`, `zensical.toml`, `.agent/rules/**` | SoT consistency, forbidden-regression searches, navigation, guardrail mirrors, stale architecture cleanup |

## Lane Rules

Subagents must:

- stay inside the assigned surface and owner boundary;
- avoid redefining architecture or product semantics;
- report findings, changed surfaces, validation, and risks back to the main thread;
- escalate cross-boundary conflicts instead of patching around them;
- avoid creating persistent prompt bundles or committed lane handoffs.

Subagents may recommend follow-up work, but the main thread decides whether it belongs in the current vertical slice.

## Vertical Slice Rule

A product feature may span several lanes. For example, a real frequency-sweep workflow touches async contracts, Backend/Runner integration, Application Workbench, and Docs/SoT consistency.

Do not let each lane independently define its own version of the workflow. The main thread owns the end-to-end contract and validates the integrated result.

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
- [Agent Skill Library](../../agent-skills/index.md)

## Agent Rule { #agent-rule }

```markdown
## Codex Subagent Coordination
- The main thread owns goal definition, SoT loading, lane selection, integration, conflict resolution, validation, and final reporting.
- Subagent work lanes are optional delegation scopes, not permanent ownership teams or fixed named agent roles.
- Use subagents only when they reduce real coordination cost.
- Recommended lanes are:
    - Julia Core + Pluto Research
    - Product Async Contracts
    - Backend + Runner Integration
    - Application Workbench
    - Python Notebook / Data Inspection
    - Docs / SoT Consistency
- Subagents must stay inside assigned folder structure and owner-boundary rules, avoid redefining architecture, and report findings/changes/risks back to the main thread.
- Cross-lane conflicts are resolved by the main thread against the relevant SoT.
- Do not create new active `Plans/` coordination artifacts or committed lane handoffs.
- Direct `develop` updates are allowed when the working tree stays coherent and touched-area checks are run.
- Long-term decisions belong in `docs/reference/**`, not temporary planning files.
- Final reports should summarize changed surfaces, validation, risks, and any skipped checks.
```
