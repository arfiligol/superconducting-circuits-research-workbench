# Task Queue / Worker Follow-up Priority

Date: 2026-03-21
Owner: codex
Status: active

## Goal

After worker isolation landed on the backend and the Reference docs were finalized, the next cleanup and implementation order must stay stable.

This file records the execution priority so later agents do not reopen the wrong layer first.

## Ordered Priority

### Priority 1: Frontend contract integration

Why first:
- backend worker-isolation contract is now richer than the frontend task client
- frontend still uses stale dispatch/event/type shapes
- frontend still does not consume `reconcile`
- frontend still derives lifecycle from mixed signals in places where docs now require single-field authority

Scope:
- refresh frontend task API contract
- align generated schema and hand-written task mappers
- consume dispatch/reconcile/event-family changes
- make submit/recovery flows handle enqueue-failed responses
- fix active refresh logic for `dispatching` and other worker-runtime states

Blocking note:
- this is the first must-do integration slice before deeper frontend refactors

### Priority 2: Simulation workflow shell decomposition

Why second:
- `SimulationWorkbenchShell` is currently a monolith mixing URL state, form state, saved setups, task attach, optimistic task state, toasts, submit orchestration, and explorer gating
- without splitting this, every future worker/task UX fix will stay expensive and fragile

Scope:
- split task attachment/recovery
- split submit orchestration
- split saved setup management
- reduce page component responsibility to composition

### Priority 3: Queue/task presenter consolidation

Why third:
- task status, lane label, queue summaries, and workflow summaries are duplicated across multiple frontend files
- this duplication will keep drifting as the backend task contract evolves

Scope:
- unify task/lane/status/reconcile presentation helpers
- remove parallel label formatters and summary builders where practical
- ensure queue/detail/worker-summary vocabulary is shared

### Priority 4: Explorer bootstrap/view split + cache

Why fourth:
- this is primarily UX/performance/extensibility work, not the first correctness gap
- it becomes cleaner after the task contract and workflow shell are already stabilized

Scope:
- bootstrap metadata once
- fetch current full-resolution view slice on demand
- cache previously viewed selections
- keep stale payload visible while the next view is loading

## Parallel Backend Track

Frontend Priority 1 can proceed independently from a backend hardening slice, as long as that backend slice does not reopen the public task contract again.

Allowed parallel backend work:
- real Redis-backed live verification
- repo-root / platform orchestration hardening
- worker bring-up / check / stop flow alignment with docs
- process-separation and responsiveness proof under live load

Not allowed in the parallel backend track:
- redesigning the task contract again
- changing `lane` / `task_kind` semantics
- reopening app-side in-process execution

## Current assessment

- canonical backend worker isolation: landed
- worker-isolation docs: finalized
- main remaining correctness gap: frontend contract integration
- main remaining maintainability gap: simulation page decomposition

