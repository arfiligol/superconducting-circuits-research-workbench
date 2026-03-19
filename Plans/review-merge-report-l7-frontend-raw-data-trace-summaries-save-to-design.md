## Review Merge Report v1

### 0) Delivery Line
- Topic: `L7-Frontend-Raw-Data-Trace-Summaries-And-Save-To-Design-UX-Fixup`
- Target Branch: `main`
- Planning & Reviewing Agent: `Codex`

### 1) Accepted Inputs
- Planning artifact:
  - [plan-artifact-v1.md](/Users/arfiligol/Github/superconducting-circuits-tutorial/Plans/plan-artifact-v1.md)
- Delivery reports:
  - user-provided `Delivery Report v1` for commit `7e815bac29e6de513e17fe525419a6954232a767`

### 2) Integrated Commits
- None yet.
- Candidate commit reviewed:
  - `7e815bac29e6de513e17fe525419a6954232a767` `fix(frontend): refine trace summary and design save ux`

### 3) Conflict Resolution
- None.

### 4) Final Verification
- `git status --short` in assigned worktree: clean
- `npm run typecheck --prefix frontend`: passed
- `npm run test --prefix frontend`: passed (`13` files / `180` tests)

### 5) Remaining Risks
- Review identified one copy/contract mismatch:
  - raw-data search placeholder now suggests `source` and `trace ID` search, but current backend search path still filters only `parameter` and `provenance_summary`
- Browser evidence supplied by Frontend Agent is Playwright-based smoke evidence against mocked session/backend routes, not live backend integration
- Latest product direction now requires a stricter `Save to Design` model than the reviewed slice implements:
  - design must be selected from a dropdown
  - new design creation must happen through a button + dialog flow
  - avoid free-text naming in the main save surface
- Current reviewed slice still uses segmented `Existing design / New design` with free-text on the new-design path
- Current backend also lacks a standalone dataset-scoped create-design mutation, so the final UX now needs additional cross-layer work
- Separate simulation task-surface UX issues remain open and are tracked in:
  - [simulation-result-task-surface-followups.md](/Users/arfiligol/Github/superconducting-circuits-tutorial/Plans/simulation-result-task-surface-followups.md)
- Local Mode execution focus is now tracked in:
  - [local-mode-research-usability-sprint.md](/Users/arfiligol/Github/superconducting-circuits-tutorial/Plans/local-mode-research-usability-sprint.md)

### 6) Mainline Status
- `Hold for redesign`

### 7) Review Basis
- SoT pages reread:
  - [component-guidelines.md](/Users/arfiligol/Github/superconducting-circuits-tutorial/docs/reference/guardrails/ui-ux-quality/component-guidelines.md)
  - [layout-patterns.md](/Users/arfiligol/Github/superconducting-circuits-tutorial/docs/reference/guardrails/ui-ux-quality/layout-patterns.md)
  - [state-management.md](/Users/arfiligol/Github/superconducting-circuits-tutorial/docs/reference/guardrails/ui-ux-quality/state-management.md)
  - [circuit-simulation.md](/Users/arfiligol/Github/superconducting-circuits-tutorial/docs/reference/app/frontend/research-workflow/circuit-simulation.md)
  - [raw-data-browser.md](/Users/arfiligol/Github/superconducting-circuits-tutorial/docs/reference/app/frontend/workspace/raw-data-browser.md)
- Code context reread:
  - [raw-data-browser-workspace.tsx](/Users/arfiligol/Github/superconducting-circuits-tutorial/frontend/src/features/data-browser/components/raw-data-browser-workspace.tsx)
  - [simulation-result-publication-card.tsx](/Users/arfiligol/Github/superconducting-circuits-tutorial/frontend/src/features/simulation/components/simulation-result-publication-card.tsx)
  - [use-simulation-publication-targets.ts](/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/implementation-frontend-raw-data-trace-summaries-and-save-to-design-ux-fixup/frontend/src/features/simulation/hooks/use-simulation-publication-targets.ts)
  - [dataset_service.py](/Users/arfiligol/Github/superconducting-circuits-tutorial/backend/src/app/services/dataset_service.py)
- UI evidence (required for user-visible frontend changes):
  - Playwright screenshot:
    - [raw-data-desktop.png](/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/implementation-frontend-raw-data-trace-summaries-and-save-to-design-ux-fixup/output/playwright/raw-data-desktop.png)
    - [simulation-existing-design.png](/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/implementation-frontend-raw-data-trace-summaries-and-save-to-design-ux-fixup/output/playwright/simulation-existing-design.png)
    - [simulation-saved-design-focus.png](/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/implementation-frontend-raw-data-trace-summaries-and-save-to-design-ux-fixup/output/playwright/simulation-saved-design-focus.png)
- Judgement:
  - The slice successfully moves the save model toward `Save to Design` and improves raw-data trace-summary density.
  - The delivery is directionally correct and verified by unit checks.
  - Mainline integration should stay on hold rather than merge immediately because:
    - the review found a minor raw-data search-copy mismatch
    - the surrounding simulation task-surface cleanup is still actively being scoped
    - the latest user-approved save-target UX now requires explicit dropdown selection plus dialog-based design creation, which this slice does not implement
