# Local Mode Research Usability Sprint

This file is an execution overlay for the current planning baseline.
It does not replace `Plans/plan-artifact-v1.md`.
Its purpose is narrower: drive the rewrite to a Local Mode state where one researcher can complete a real research loop without needing Online Mode.

## 0) Task Information

- Agent: `Planning Agent`
- Task ID / Topic: `L8-Local-Mode-Research-Usability`
- Status: `Active planning checkpoint 2026-03-19`

## 0.1) Execution Checkpoint (2026-03-19)

- Merged on `main`:
  - backend explicit dataset-scoped design creation
  - simulation publication support for explicit `design_id` targets
  - frontend `Save to Design` adoption with design dropdown + `New Design` dialog
  - simulation-result task-surface cleanup that removes the misleading task-heavy wall
- Immediate consequence:
  - `LM1` is now effectively merged on `main` across backend and frontend
  - `LM2` is merged far enough to materially clean the page and remove misleading task wording
  - the next active needs shift to `LM3` raw-data continuity/copy truthfulness and `LM4` characterization runnable workflow

## 1) Goal

- Reach a Local Mode workflow where a researcher can:
  1. choose a circuit definition and run a simulation
  2. save the useful simulation result into an explicit design inside the active dataset
  3. open the saved traces in Raw Data
  4. choose the same design in Characterization
  5. run at least one basic characterization analysis
  6. inspect the persisted result and apply identify tags when needed

## 2) Scope

### In Scope

- `Circuit Simulation`
- `Raw Data`
- `Characterization`
- Local shell/task behavior only where it directly affects the research workflow

### Out of Scope For This Sprint

- `Online Mode`
- auth/session provider decisions
- workspace collaboration
- generic task-management expansion inside workflow pages
- large page-local infrastructure diagnostics

## 3) Current Verified State

### Already usable enough to build from

- Local shell/runtime shape already exists and follows the `Local Mode` baseline closely enough to keep the user inside one app shell.
- `Circuit Simulation` already supports simulation submission, attached run recovery, result exploration, and persisted result publication at the backend contract level.
- Persisted simulation publication already materializes dataset/design-owned traces that the Raw Data backend can browse.
- `Raw Data` already has a design list, trace-summary list, and single-trace preview flow.
- `Characterization` already has:
  - design browse
  - persisted result list
  - run history
  - result detail
  - identify/tagging

### Current main-branch gaps

#### 1. `Save to Design` is now merged for `Simulation Result`

- `main` now supports the approved simulation publication model:
  - design dropdown
  - `New Design` dialog
  - create-then-select behavior
  - publish by explicit `design_id`
- The active remaining concern is no longer the save-target model itself.
- The next continuity concern is how clearly the saved design flows into `Raw Data` and then into `Characterization`.

#### 2. Simulation task presentation is improved, but global task-selection work remains open

- `main` no longer shows the previous task-heavy summary wall in `Simulation Result`.
- Misleading `View Task` wording has been removed in favor of truth-based attach wording.
- Remaining gap:
  - page-level task presentation is cleaner, but `Global Context` still does not yet own the broader task selection / inspection flow the user wants
  - compatible task switching across workflow pages remains a later shell-and-workflow integration slice

#### 3. Raw Data continuity is partially present, but the cleanup slice is not final on `main`

- Main already has the improved top-down layout, but trace-summary filter copy and density cleanup are still unfinished on `main`.
- The reviewed frontend slice improves this area, but one copy mismatch remains:
  - the new placeholder suggests search by `source` and `trace ID`
  - backend search still filters by `parameter` and `provenance_summary` only

#### 4. Characterization is still browse-first, not run-first

- The SoT page for Characterization defines a full flow:
  - `Choose Design -> Select Traces -> Run Analysis -> Review Latest Run -> Review Persisted Result`
- Current rewrite implementation does not meet that flow yet.
- `frontend/src/features/characterization/components/characterization-workspace.tsx` explicitly says:
  - `This registry does not submit or attach analyses.`
- Current source-contract tests also explicitly assert the absence of a run CTA and submit hook.
- Current frontend task submission typing has no characterization-specific payload.
- Current backend task submission parsing/domain model also has no characterization-specific setup contract.
- Current Local Mode processor summary in `backend/src/app/services/task_service.py` still reports the characterization lane as:
  - `offline`
  - `execution_mode: not_configured`
  - `capacity: 0`
- Result: the page can inspect persisted characterization output, but it cannot yet drive new characterization work from Local Mode.

## 4) Planning Judgement

- The current formal baseline in `Plans/plan-artifact-v1.md` is still dominated by session/auth/workspace rebaseline work.
- That baseline remains valid as the broad rewrite plan.
- For near-term product value, Local Mode research usability should now be treated as the active execution focus for workflow surfaces.
- The fastest path is not to build more shell/task UI first.
- The fastest path is to complete the actual research loop first, while keeping shell-owned context in the shell.

## 5) Local Mode Research Loop Definition

### The loop is considered complete only when all of the following are true

1. A simulation result can be saved into an explicitly chosen design in the active dataset.
2. Creating a new design does not rely on typing the final target name into the main card.
3. The saved design appears in Raw Data immediately and is easy to open.
4. Characterization can select that design and submit at least one basic analysis.
5. Characterization results persist and can be reopened after refresh.
6. Workflow pages remain result-first and analysis-first, not task-wall-first.

## 6) Implementation Slices

### LM1 Simulation save target finalization

- Goal: replace the current free-text save model with an explicit design-target workflow.
- Required behavior:
  - existing designs come from the active dataset browse model
  - the save card uses a dropdown for design selection
  - `New Design` opens a small dialog
  - dialog creation returns a real design row that becomes selectable immediately
  - the main save action publishes by `design_id`, not by guessed slug
- Backend status:
  - delivered on `main`
- Frontend status:
  - delivered on `main`
- Mainline result:
  - the simulation publication flow now uses a design dropdown
  - `New Design` uses a dialog-backed explicit create flow
  - publish-by-`design_id` is the primary user path

### LM2 Simulation task-surface cleanup

- Goal: make `Simulation Result` read as a clean workflow stage instead of a task dashboard.
- Required behavior:
  - remove or demote `View Task` from the page unless it truly opens a distinct task surface
  - shrink page-local task state to concise tags or short inline metadata
  - move task switching and deeper task inspection into `Global Context`
  - keep `SimulationResultExplorer` as the visual primary surface
- Status on `main`:
  - partially merged
  - the page is materially cleaner and the misleading task-heavy wall is removed
  - deeper `Global Context` ownership of task switching still remains for a later slice

### LM3 Raw Data continuity and density cleanup

- Goal: make published simulation output visibly arrive in Raw Data without extra interpretation cost.
- Required behavior:
  - compact trace-summary labels and filters
  - correct the search placeholder to match backend truth
  - preserve the master-detail structure already on `main`
  - provide a clear path from saved simulation result to the saved design in Raw Data

### LM4 Characterization runnable workflow

- Goal: turn Characterization from a persisted-result browser into a runnable Local Mode analysis workbench.
- Required behavior:
  - choose design from the active dataset
  - choose compatible traces
  - choose analysis
  - provide only the minimum config fields needed for that analysis
  - submit a characterization task
  - show compact latest-run state
  - reopen persisted results and tagging after completion
- Required cross-layer work:
  - add characterization submission contract to frontend typing
  - add characterization submission parsing/domain contract on the backend
  - keep latest-run state compact and shell-compatible

### LM5 Characterization minimum analysis set

- Goal: land a small but real analysis set that is enough for Local Mode research work.
- Planning direction:
  - first runnable candidate should be `Admittance Extraction`
    - it already exists in the rewrite characterization registry, run-history fixtures, and persisted result detail fixtures
  - second candidate should be chosen by reconciling rewrite and NiceGUI legacy value
    - likely candidates to review:
      - `S21 Resonance Fit`
      - `SQUID Fitting`
      - `Y11 Response Fit`
      - current rewrite-side `Sideband Comparison`
- Rule:
  - do not try to port every legacy analysis in one slice
  - ship one stable analysis path first, then add the next most research-useful path

### LM6 Local Mode research verification

- Goal: verify the end-to-end research loop in Local Mode, not only isolated UI pieces.
- Required checks:
  - simulation run -> save to design -> raw data browse
  - raw data design -> characterization selection
  - characterization run -> persisted result detail -> identify tagging
  - refresh recovery for saved design and persisted characterization result

## 7) Recommended Execution Order

1. `LM3` raw-data continuity + copy truthfulness
2. `LM4` characterization submission contract and runnable workflow
3. `LM5` first basic analysis path
4. `LM6` Local Mode end-to-end verification

## 8) Immediate Next Implementation Recommendation

- The next implementation should move to `LM4`, with `LM3` handled just before it or alongside it as a small cleanup slice.
- Reason:
  - the simulation save-target model is now in place on `main`
  - `Simulation Result` is already materially cleaner than before
  - the real remaining Local Mode blocker is that `Characterization` still cannot drive new runnable analysis work
- Concrete target:
  - characterization submission contract
  - trace selection + analysis selection
  - compact latest-run state
  - first basic runnable analysis path

## 9) Notes On Existing Reviewed Frontend Delivery

- Reviewed commit:
  - `7e815bac29e6de513e17fe525419a6954232a767`
- Current judgement:
  - useful reference for trace-summary cleanup
  - no longer the active reference for simulation save-target UX now that `L8` is merged on `main`
  - its remaining planning value is mainly the Raw Data cleanup direction, not the final `Save to Design` implementation

## 10) Verification Commands

- Frontend:
  - `npm run typecheck --prefix frontend`
  - `npm run test --prefix frontend`
- Backend:
  - `cd backend && uv run pytest -q`
  - `cd backend && uv run ruff check`
