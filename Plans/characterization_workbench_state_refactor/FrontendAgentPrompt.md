# Frontend Agent Prompt: Characterization Workbench State Refactor

## Task Information
- Agent: Frontend Agent
- Role: frontend
- Task ID / Topic: `characterization-workbench-state-refactor`
- Base branch: `develop`
- Required plan: `Plans/characterization_workbench_state_refactor/Plan.md`
- Branch / Worktree:
  - Branch: `codex/frontend-characterization-workbench-state-refactor`
  - Worktree: `/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/frontend-characterization-workbench-state-refactor`

## Goal
Refactor `/characterization` state ownership so the page no longer flickers or rewrites explicit
result selection. Do not solve this with a temporary one-line fallback patch. The page needs a
clear frontend architecture for route intent, dataset/design scope, task context, result selection,
pipeline draft state, detail loading, and URL synchronization.

The triggering failure is:

```text
http://localhost:3000/characterization?datasetId=local-floatingqubit-100&taskId=490&designId=design_floatingqubitwithxy&resultId=char-admittance-run-24
```

The page eventually switches Result Preview to `char-admittance-run-25`, even though
`char-admittance-run-24` is a valid result for the requested design. Task 490 points at analysis
run 25, but explicit route `resultId=char-admittance-run-24` must own Result Preview.

## Read First
1. Read `Plans/characterization_workbench_state_refactor/Plan.md`.
2. Read these SoT / guardrails:
   - `docs/reference/app/frontend/research-workflow/characterization.md`
   - `docs/reference/app/backend/characterization-results.md`
   - `docs/reference/guardrails/ui-ux-quality/state-management.md`
   - `docs/reference/guardrails/ui-ux-quality/routing.md`
   - `docs/reference/guardrails/ui-ux-quality/component-guidelines.md`
   - `docs/reference/guardrails/execution-verification/testing.md`
3. Inspect current code:
   - `frontend/src/features/characterization/components/characterization-workspace.tsx`
   - `frontend/src/features/characterization/hooks/use-characterization-workflow-data.ts`
   - `frontend/src/features/characterization/lib/workflow.ts`
   - `frontend/src/features/characterization/hooks/use-characterization-result-explorer.ts`
   - `frontend/src/features/characterization/lib/api.ts`
   - `frontend/tests/characterization-workflow.test.ts`

## Required Outcome
Implement a maintainable frontend refactor where state ownership is explicit:

- Route Intent parses and preserves shareable URL state.
- Active Dataset and Design Scope resolution are separate from result selection.
- Task Context can hydrate run/pipeline context, but cannot override an explicit route result.
- Result Selection has deterministic priority:
  1. Valid explicit route `resultId`
  2. User-clicked result
  3. Completed result from a submit in this page session
  4. Task handoff result only when no explicit route/user result exists
  5. Results-list default
- Result Detail loading may fetch a direct route result even if the result list is empty or stale.
- URL Sync is late/gated and must not write fallback result ids while explicit route result is still
  pending validation.
- URL Sync must preserve `datasetId` and unrelated query params.
- Existing page functionality must remain:
  - Design / Source Scope
  - Data Collection Review
  - Analysis Pipeline
  - Active Analysis Run
  - Result Preview
  - Downstream Analysis / Next Step
  - Artifact explorer
  - Identify/tagging flow

## Architecture Expectations
You may choose exact filenames, but avoid leaving all logic in one giant hook/component. Prefer a
small set of focused hooks and pure helpers. A good target boundary is:

- `frontend/src/features/characterization/lib/workflow.ts`
  - pure route/result/design/task resolution helpers
- `frontend/src/features/characterization/hooks/use-characterization-route-state.ts`
  - route parsing and canonical URL sync intent
- `frontend/src/features/characterization/hooks/use-characterization-scope-data.ts`
  - design/traces/registry/history/results fetching for a resolved dataset/design
- `frontend/src/features/characterization/hooks/use-characterization-result-selection.ts`
  - result selection priority and detail query coordination
- `frontend/src/features/characterization/hooks/use-characterization-pipeline-draft.ts`
  - trace/analysis/config draft state
- `frontend/src/features/characterization/components/*`
  - split obvious local sections if needed, but preserve the existing visual language

These names are suggestions, not strict allowed files. The important part is clear ownership and
testable behavior.

## Allowed Area
- `frontend/src/features/characterization/**`
- `frontend/tests/characterization-workflow.test.ts`
- Other frontend tests only if directly needed.

## Do Not Touch
- Backend implementation and API contracts.
- Data ingestion, raw data, simulation pages, unless a shared frontend type import adjustment is
  unavoidable.
- `data/**`
- `.playwright-mcp/**`
- Old rejected/prototype worktrees.
- `Plans/**` unless you need to add a short implementation note in your Delivery Report instead.

## Non-Goals
- Do not implement downstream fitting analysis.
- Do not redesign the Characterization visual UI from scratch.
- Do not add backend compatibility shims.
- Do not fake successful behavior with hardcoded result ids.
- Do not rely on result list ordering to resolve explicit URL result selection.

## Required Tests
Add or update deterministic tests for:

- `requestedResultId=char-admittance-run-24` with result rows ordered `[25, 24]` resolves to 24.
- `taskId=490` pointing at run 25 does not override explicit `resultId=24`.
- Direct route result detail remains loadable when the results list is empty or stale.
- Missing/stale result rebounds only after evidence proves it unavailable.
- URL sync preserves `datasetId`.
- Hook/source boundary: URL replace should not be hidden in data-fetching hooks.

Existing tests should continue to pass.

## Verification
Run at minimum:

```bash
git diff --check
npm run typecheck --prefix frontend
npm run test --prefix frontend -- characterization-workflow.test.ts
npm run test --prefix frontend
```

If practical, run a local browser smoke against:

```text
http://localhost:3000/characterization?datasetId=local-floatingqubit-100&taskId=490&designId=design_floatingqubitwithxy&resultId=char-admittance-run-24
```

Expected browser outcome:
- URL remains scoped to `char-admittance-run-24` after SWR/task refresh.
- Result Detail title/payload remains run 24.
- Active Analysis Run may still show task 490 context, but it does not switch Result Preview to run
  25.

If live browser setup is not available, state that clearly in the Delivery Report.

## Handoff
Return a Delivery Report v1 with:

- Commit hash.
- Changed files and why they changed.
- State architecture summary: what owns route intent, result selection, task context, URL sync.
- Tests added/updated.
- Verification commands and results.
- Browser smoke evidence if run.
- Known risks or any product semantics that need docs promotion.

Do not merge back to `develop`; Planning & Reviewing Agent will review and integrate.
