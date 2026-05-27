# Test Agent Prompt: Design Scope Lifecycle Integration and E2E Verification

## 0) Task Information

- Agent: Test Agent
- Lane: Test / Integration
- Task ID / Topic: Design Scope lifecycle integrated verification
- Prompt Level: `L2 Slice`
- Branch: `codex/design-scope-lifecycle-integration-test`
- Worktree: `/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/design-scope-lifecycle-integration-test`
- Base: an integration branch or `develop` containing accepted docs commit `79c739bd6a29f1b7520cc2334944c4e47d6911bc` plus accepted Backend and Frontend DesignScope lifecycle commits.

Before editing, verify that the required commits are ancestors of the base branch. If Backend/Frontend commits are not supplied in the prompt, stop and ask Planning & Review for the exact base.

## 1) Goal

Verify that the integrated application supports the user workflow:

- HFSS/layout data and circuit-simulation data can be targeted into the same dataset-local `DesignScope`.
- DesignScope lifecycle actions are backend-owned and visible in UI.
- Merge re-parents metadata/read models without moving TraceStore payloads.
- Characterization uses `dataset_id + design_id` correctly and rejects stale cross-scope result/task leakage.

## 2) Read First

- `Plans/design_scope_lifecycle/DesignScopeLifecyclePlan.md`
- `docs/reference/data-formats/dataset-record.md`
- `docs/reference/app/backend/datasets-results.md`
- `docs/reference/app/frontend/workspace/data-ingestion.md`
- `docs/reference/app/frontend/workspace/raw-data-browser.md`
- `docs/reference/app/frontend/research-workflow/circuit-simulation.md`
- `docs/reference/app/frontend/research-workflow/characterization.md`
- Backend and Frontend Delivery Reports for the implementation slices.

## 3) Allowed Area

- Backend integration tests.
- Frontend tests.
- Playwright/browser smoke scripts or evidence under existing output folders.
- Test fixtures only when they are synthetic and repo-owned.

## 4) Do Not Touch

- Production code unless Planning & Review explicitly converts this into a fixup task.
- `data/raw/**`; it is read-only.
- Do not make real PF6FQ raw data required by default test suites.
- Do not re-enable heavy real-data tests without explicit env gating.

## 5) Required Coverage

### Default Synthetic Integration

- Create dataset and create two design scopes.
- Ingest synthetic layout-simulation trace into existing target scope by explicit `design_id`.
- Publish/save synthetic circuit-simulation trace into the same target scope by explicit `design_id`.
- Verify Raw Data design row source coverage includes both `layout_simulation` and `circuit_simulation`.
- Verify Characterization registry sees eligible traces inside the same `dataset_id + design_id`.
- Verify create-new ingestion does not hidden-match an existing design name and returns conflict / select-existing guidance when appropriate.
- Rename scope preserves `design_id`.
- Archive/delete removes the scope from normal target selectors and blocks new ingest/publication/characterization submissions.
- Merge source into target:
  - source becomes archived with `redirect_design_id`.
  - target trace list includes re-parented traces.
  - run/result history follows the target where applicable.
  - stale source deep link resolves according to backend contract.

### Frontend Unit / Component Contract

- Data Ingestion target selector sends explicit target shape.
- Raw Data lifecycle dialogs are gated by backend `allowed_actions`.
- Merge success clears stale trace selection/preview.
- Characterization does not flicker between stale result loading and stale result error when `taskId` belongs to another design scope.

### Real Data Opt-In

Real PF6FQ data tests are opt-in only:

```bash
RUN_HFSS_REAL_DATA_E2E=1
PF6FQ_RAW_DATA_ROOT=/Users/arfiligol/Github/superconducting-circuits-tutorial/data/raw/layout_simulation/PF6FQ
```

When enabled, verify at least:

- `PF6FQ_Q0_XY_Im_Y11.csv` parses/imports as `[frequency, L_jun]` ND grid.
- Import targets an existing PF6FQ Q0 DesignScope by explicit `design_id`.
- A second compatible source can land in the same target scope.
- Characterization can open the selected scope without stale result flicker.

## 6) Verification Commands

Default checks:

```bash
git diff --check
cd backend && uv run ruff check
cd backend && uv run pytest -q tests/test_rewrite_catalog.py tests/test_local_characterization_integration.py tests/test_characterization_results_integration.py
npm run typecheck --prefix frontend
npm run test --prefix frontend -- data-browser.test.ts simulation-workflow.test.ts characterization-workflow.test.ts
```

Run newly added focused tests explicitly and report exact names.

If feasible:

```bash
cd backend && uv run pytest -q
npm run test --prefix frontend
```

Opt-in real-data checks must be reported separately and must skip by default when the env var is not set.

Browser verification:

- Use a real local backend/frontend when possible.
- Verify `/data-ingestion`, `/raw-data`, and `/characterization` through the user-visible flow.
- Capture screenshot/text/requests evidence under `frontend/output/playwright/`.

## 7) Handoff

Use `Delivery Report v1` and include:

- Branch/worktree and commit hash if tests are committed.
- The exact Backend and Frontend commits used as base.
- Changed test files.
- Default verification results.
- Opt-in real-data verification results, clearly separated.
- Browser evidence paths.
- Any remaining blockers, especially queue/runtime gaps versus repository/runtime direct verification.

