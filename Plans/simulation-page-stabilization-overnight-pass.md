# Simulation Page Stabilization Overnight Pass

This file is an execution artifact for the current overnight implementation pass.
It does not replace `Plans/local-mode-research-usability-sprint.md`.
Its purpose is narrower: finish the current Simulation page usability/stability gaps in one uninterrupted pass and verify them with real browser automation.

## 0) Task Information

- Agent: `Codex`
- Task ID / Topic: `L11-Simulation-Page-Stabilization`
- Status: `Active execution checkpoint 2026-03-20`

## 1) Scope

### In Scope

- `Circuit Simulation` page user-facing workflow
- shared transient message surface for workflow success/error feedback
- `Simulation Result` and `Post Processing Result` explorer controls
- `Post Processing Setup` step authoring correctness
- Playwright validation for the full page using `FloatingQubitWithXYLine`

### Out of Scope

- Raw Data new feature work beyond continuity validation
- Characterization feature expansion
- Online Mode
- auth/session/global shell redesign

## 2) Problems To Fix In This Pass

### A. Page-level status cards are too heavy

- `Run submission failed`
- `Simulation Setup · Completed`
- similar transient status banners

These should move to a stacked toast/message pattern so the page body stays focused on the workflow itself.

### B. Post-processing submit contract is still stale

- backend still requires `post_processing_setup.output_view`
- frontend no longer authors that field

The contract must be corrected so Stage 4 remains process-authoring only.

### C. Post-processing basis labels are not step-aware

- after `Coordinate Transformation`, downstream `Kron Reduction` still shows numeric ports only
- desired behavior:
  - `Port CM`
  - `Port DM`
  - remaining untouched numeric ports such as `Port 3`

### D. Result explorers still do not support parameter-sweep point selection

- current result explorers let the user choose family/source/metric/ports
- they do not yet let the user choose which parameter-sweep point is being inspected

Required product direction:
- if result data includes parameter sweeps, insert one compact card between the top selector block and the result view
- each sweep dimension gets its own selector
- the current plot/table updates to the chosen sweep point

### E. Full live verification is still missing

- the page must be tested end-to-end using the real `FloatingQubitWithXYLine` schema
- coverage must include:
  - simulation submit
  - result browse
  - `Save Current Trace`
  - PTC visibility
  - post-processing step authoring
  - post-processing submit/run/result
  - parameter sweep point selection if available

## 3) Working Decisions For This Pass

1. Use one shared toast/message component instead of page-local ad hoc banners.
2. Keep the page body quiet once a toast exists; do not duplicate the same transient message inside the stage card.
3. Treat `Post Processing Setup` as authoring only:
   - steps
   - order
   - note
   - submit
4. Derive downstream post-processing basis labels from the preceding steps, not only from the original definition ports.
5. Treat parameter sweep selection as result-browse state, not setup state.
6. Prefer backend truth over frontend guesswork for explorer data whenever the API already exposes enough structure.
7. If a backend contract must change to make the UI truthful, change the contract instead of keeping a misleading compatibility shim.

## 4) Acceptance Criteria

The pass is complete only when all of the following are true:

1. Submitting post-processing no longer fails with `post_processing_setup.output_view is required`.
2. Workflow success/error feedback appears as stacked transient toasts, not large blocking page banners.
3. After a coordinate transform on ports 1 and 2, downstream Kron Reduction choices reflect the transformed basis:
   - `Port CM`
   - `Port DM`
   - `Port 3`
4. `Simulation Result` and `Post Processing Result` can inspect parameter-swept results by explicitly choosing the sweep point.
5. `FloatingQubitWithXYLine` can be used to run through the page end-to-end in Local Mode.
6. The browser validation captures screenshots/evidence for the key workflow states.
7. The important browser flow can be translated into a durable E2E regression test.

## 5) Validation Expectations

### Code Validation

- `npm run typecheck --prefix frontend`
- `npm run test --prefix frontend`
- targeted backend tests for touched task/explorer/post-processing areas
- broader backend test run if touched backend contracts materially change

### Browser Validation

- use Playwright CLI / interactive browser checks
- verify the actual page with the `FloatingQubitWithXYLine` definition
- store artifacts under `output/playwright/`

### E2E Follow-through

- when the live browser pass is stable, convert the critical workflow into a repository test that protects the core Simulation page loop

## 6) Open Decisions To Record For Later Review

- exact toast placement:
  - default implementation target is bottom-right stacked toasts
- exact parameter-sweep selector visual form:
  - default implementation target is one compact selector row/card between selector block and result view
- if a real backend limitation blocks a fully truthful sweep selector, record it explicitly rather than masking it in the UI

## 7) Implementation Completed

### A. Shared transient workflow toasts

- Added a shared stacked toast system for workflow feedback.
- Location:
  - `frontend/src/lib/app-state/toasts.tsx`
  - `frontend/src/lib/app-state/index.tsx`
- Applied to Simulation page submission and completion/failure feedback.
- Page-level transient banners/cards no longer carry:
  - `Run submission failed`
  - `Simulation Setup · Completed`
  - `Post Processing Setup · Completed`

### B. Parameter sweep point selection in result explorers

- `Simulation Result` and `Post Processing Result` explorers now expose a dedicated `Parameter Sweep Point` card when the result includes sweeps.
- Each sweep dimension renders its own selector.
- The selected sweep point updates:
  - explorer bootstrap selection
  - plot payload
  - trace-scoped save identity
- Backend now exposes stable selection-level `sweep_index` and trace identity metadata.

### C. Step-aware post-processing basis

- Added step-basis derivation logic in:
  - `frontend/src/features/simulation/lib/post-processing-basis.ts`
- After `Coordinate Transformation` on ports 1 and 2, downstream `Kron Reduction` choices now reflect:
  - `Port CM`
  - `Port DM`
  - untouched numeric ports such as `Port 3`

### D. Post-processing authoring contract correction

- Backend no longer requires `post_processing_setup.output_view` for new writes.
- `Post Processing Setup` remains authoring-only.
- `Post Processing Result` is the authoritative source/family/metric/port browser.

### E. Trace-scoped save remains explorer-local

- `Save Current Trace` stays embedded in the explorer surface.
- It works for both:
  - `Simulation Result`
  - `Post Processing Result`
- Save dialog still supports:
  - existing design
  - `New Design`

### F. Durable E2E regression added

- Added a real Playwright E2E test:
  - `tests/app/e2e/test_rewrite_simulation_page_playwright.py`
- The test boots isolated backend/frontend processes with temp sqlite state and uses the real:
  - `FloatingQubitWithXYLine`
  - simulation submit
  - parameter sweep
  - PTC
  - trace save
  - CT -> Kron
  - post-processing submit
  - post-processing result browse

## 8) Overnight Verification Result

### Automated Verification

- `npm run typecheck --prefix frontend`
- `npm run test --prefix frontend`
- `cd backend && uv run pytest -q tests/test_simulation_result_explorer.py tests/test_simulation_result_publication.py tests/test_session_and_tasks.py`
- `cd backend && uv run pytest -q`
- `cd backend && uv run ruff check src/app/api/routers/tasks.py src/app/domain/result_traces.py src/app/domain/tasks.py src/app/infrastructure/simulation_result_publication_materializer.py src/app/services/simulation_result_explorer_service.py src/app/services/task_service.py tests/test_simulation_result_explorer.py tests/test_simulation_result_publication.py tests/test_session_and_tasks.py`
- `env RUN_REWRITE_SIMULATION_PAGE_E2E=1 uv run pytest -q tests/app/e2e/test_rewrite_simulation_page_playwright.py`

### Results

- Frontend typecheck: passed
- Frontend tests: `13` files / `180` tests passed
- Targeted backend tests: `70 passed`
- Full backend tests: `193 passed`
- Targeted backend ruff: passed
- Playwright E2E: `1 passed`

## 9) Live Workflow Covered By The E2E

The durable browser test now covers:

1. Create and use the persisted `FloatingQubitWithXYLine` definition.
2. Enable simulation parameter sweep on `L_jun`.
3. Enable PTC and compensate all three ports.
4. Run simulation and validate toast-based feedback.
5. Browse `Simulation Result`, including sweep point selection.
6. Switch to `Y Matrix` and verify `PTC` source availability.
7. Save the current trace into a design.
8. Add `Coordinate Transformation`.
9. Add `Kron Reduction` and verify transformed basis labels.
10. Run post-processing and validate toast-based feedback.
11. Browse `Post Processing Result`.
12. Verify:
   - `Raw -> S / Y / Z`
   - `PTC -> Y / Z`

## 10) Decisions Taken During This Pass

1. Toasts are the default transient workflow feedback surface.
2. Toast placement is bottom-right stacked with auto-dismiss.
3. Parameter sweep selection belongs to explorer browse state, not setup state.
4. Post-processing downstream basis must derive from prior steps instead of the original definition ports only.
5. E2E selectors use stable `data-testid` on inline selects where accessibility-only labels proved too brittle for regression coverage.

## 11) Remaining Review Notes

1. The overnight E2E covers the real Local Mode loop, but only one sweep dimension was exercised live with this schema.
2. Multi-axis sweep UI is implemented structurally, but a separate regression fixture would be useful if multi-dimensional sweeps become common.
3. Toast text is now the primary transient feedback channel, so future stage-level messages should avoid duplicating the same transient state in the page body.
