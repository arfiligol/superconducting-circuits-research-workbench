# Frontend Agent Prompt: Target Design Scope UX and Lifecycle UI

## 0) Task Information

- Agent: Frontend Agent
- Lane: Frontend
- Task ID / Topic: Target Design Scope UX and DesignScope lifecycle UI
- Prompt Level: `L3 Milestone`
- Branch: `codex/frontend-design-scope-lifecycle`
- Worktree: `/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/frontend-design-scope-lifecycle`
- Base: `develop` after docs commit `79c739bd6a29f1b7520cc2334944c4e47d6911bc` is merged

Before editing, verify:

```bash
git merge-base --is-ancestor 79c739bd6a29f1b7520cc2334944c4e47d6911bc develop
```

If this exits non-zero, stop and report that `develop` is stale. Do not make code changes.

## 1) Current Problem

Data Ingestion still behaves like a free-text design-name flow, and Raw Data can browse design scopes but not manage lifecycle. The user needs to explicitly choose an existing `Target Design Scope` or create a new one so HFSS layout data and circuit simulation data can land in the same scope.

The frontend must treat lifecycle as backend-owned:

- Existing target means explicit `dataset_id + design_id`.
- Free-text names are only create-new defaults.
- Merge / archive / delete must call backend lifecycle APIs.
- Frontend must not re-parent traces, parse `store_ref`, or fake merge locally.

## 2) Read First

- `docs/reference/app/frontend/workspace/data-ingestion.md`
- `docs/reference/app/frontend/workspace/raw-data-browser.md`
- `docs/reference/app/frontend/research-workflow/circuit-simulation.md`
- `docs/reference/app/frontend/research-workflow/characterization.md`
- `docs/reference/app/backend/datasets-results.md`
- `docs/reference/data-formats/dataset-record.md`
- `docs/reference/guardrails/ui-ux-quality/state-management.md`
- `docs/reference/guardrails/ui-ux-quality/component-guidelines.md`
- `Plans/design_scope_lifecycle/DesignScopeLifecyclePlan.md`

## 3) Allowed Area

- `frontend/src/features/data-browser/**`
- `frontend/src/features/simulation/**`
- `frontend/src/features/characterization/**` only for scoped stale-link handling and design lifecycle fields.
- Shared frontend API/type helpers used by those feature areas.
- Frontend tests.

## 4) Do Not Touch

- `backend/**`
- `docs/**`
- `data/raw/**`
- Do not add frontend-only merge/re-parent logic.
- Do not introduce a global active design context.
- Do not make browser smoke with mocked API interception sound like real-backend verification.

## 5) Required Outcome

### Data Ingestion

- Replace free-text-only `Design Name` authority with a `Target Design Scope` control.
- Support two explicit modes:
  - select existing active scope from backend design rows.
  - create new scope using a display name.
- Keep filename-derived HFSS suggestions only as create-new defaults.
- For existing target imports, submit explicit `design_id`.
- For create-new imports, submit create-new intent/name through the backend-supported request shape.
- Multi-file PF6FQ ingestion must apply the same target decision consistently across files.
- Show per-file import status without hiding target-scope errors.

### Raw Data Browser

- Extend design scope panel to show lifecycle state, redirect target if present, allowed actions, and mutation policy summary.
- Add backend-backed UI flows for:
  - create design scope.
  - rename.
  - merge selected source into another active target.
  - archive/delete where backend allows.
- Destructive operations require confirmation dialogs.
- After merge/archive/delete, clear stale trace selection/preview and use returned backend rows to update UI.
- If selected design becomes archived with redirect, show a concise stale-link notice and switch to the target when backend response provides it.

### Circuit Simulation

- Align trace/result save or publication surfaces with the same `Target Design Scope` model:
  - existing target sends `design_id`.
  - create-new sends display name/create intent.
  - no hidden name match.
- Preserve existing successful simulation save behavior and tests.

### Characterization

- Consume lifecycle fields safely.
- Normal selector should use active design scopes.
- Archived/deleted/redirected design state must not show as a normal runnable analysis target.
- Preserve the recent stale task/result guard: a task/result from another design scope must not pull the page away from the requested `designId`.

## 6) Constraints

- Use SWR for server state and feature hooks/services for API calls.
- Keep direct fetches out of components.
- Use app-owned controls/dialogs from existing UI primitives.
- Keep error, empty, and recovery copy concise.
- Keep dense pages focused; do not add duplicated shell context cards.
- If Backend Agent endpoint shape is not yet merged, centralize assumptions in `frontend/src/features/data-browser/lib/api.ts` or equivalent and state them clearly in the report.

## 7) Verification

Run at minimum:

```bash
git diff --check
npm run typecheck --prefix frontend
npm run test --prefix frontend -- data-browser.test.ts simulation-workflow.test.ts characterization-workflow.test.ts
```

If changes touch many shared frontend contracts, also run:

```bash
npm run test --prefix frontend
```

Add or update tests proving:

- Data Ingestion existing target sends `design_id`.
- Data Ingestion create-new uses suggestion as default but does not hidden-match an existing scope.
- Multi-file ingestion keeps one target decision.
- Raw Data lifecycle action buttons are gated by backend `allowed_actions`.
- Merge dialog requires an active target and clears stale trace preview/selection after success.
- Simulation save/publish keeps explicit target behavior.
- Characterization ignores out-of-scope task/result state and does not present archived/deleted scopes as runnable.

Browser verification:

- Run a real local browser smoke for `/data-ingestion` target selection.
- Run a real local browser smoke for `/raw-data` rename/merge/archive UI after backend lifecycle APIs are available.
- Capture screenshot/text evidence in `frontend/output/playwright/`.

## 8) Handoff

Use `Delivery Report v1` and include:

- Branch/worktree and commit hash.
- Changed files with reason.
- API assumptions or backend endpoint shape consumed.
- Tests and browser evidence.
- Known risks, especially any UI path that still depends on backend lifecycle API finalization.

