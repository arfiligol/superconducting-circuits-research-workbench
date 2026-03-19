# Local Mode Research Usability Sprint

This file is an execution overlay for the current planning baseline.
It does not replace `Plans/plan-artifact-v1.md`.
Its purpose is narrower: drive the rewrite to a Local Mode state where one researcher can complete a real research loop without needing Online Mode.

## 0) Task Information

- Agent: `Planning Agent`
- Task ID / Topic: `L8-Local-Mode-Research-Usability`
- Status: `Active planning checkpoint 2026-03-19`

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

#### 1. `Save to Design` is not finished

- `frontend/src/features/simulation/components/simulation-result-publication-card.tsx` on `main` still presents `Save to Dataset` and uses free-text `designName`.
- The reviewed frontend slice `7e815bac29e6de513e17fe525419a6954232a767` improves the model, but it still uses `Existing design / New design` with free-text entry on the new-design path.
- The latest product direction is stricter:
  - design must be chosen from a dropdown
  - creating a new design must happen through a button + dialog flow
  - once created, the new design must immediately appear in the dropdown
  - avoid typo-prone free-text naming in the main save surface

#### 2. There is no standalone create-design contract yet

- Current dataset router exposes `GET /datasets/{dataset_id}/designs` but not a dataset-scoped create-design mutation.
- Current simulation publication can still materialize a new design implicitly from `design_name` plus slug derivation.
- That implicit behavior is not enough for the desired UX because it does not provide an explicit create-select-confirm loop.

#### 3. Simulation task presentation is still too heavy

- `frontend/src/features/simulation/components/simulation-workbench-shell.tsx` still renders a task-dense block in `Simulation Result`, including:
  - `Attached Run`
  - `Result Availability`
  - `Downstream State`
  - extra task support disclosure
- `View Task` is also misleading there because it only re-attaches the task instead of opening a distinct task surface.

#### 4. Raw Data continuity is partially present, but the cleanup slice is not final on `main`

- Main already has the improved top-down layout, but trace-summary filter copy and density cleanup are still unfinished on `main`.
- The reviewed frontend slice improves this area, but one copy mismatch remains:
  - the new placeholder suggests search by `source` and `trace ID`
  - backend search still filters by `parameter` and `provenance_summary` only

#### 5. Characterization is still browse-first, not run-first

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
- Required backend follow-up:
  - add a dataset-scoped create-design mutation or equivalent explicit creation authority
  - do not keep relying on implicit name-to-slug creation as the primary UX contract
- Notes:
  - the already-reviewed frontend slice is a useful reference, but it is not the final implementation target

### LM2 Simulation task-surface cleanup

- Goal: make `Simulation Result` read as a clean workflow stage instead of a task dashboard.
- Required behavior:
  - remove or demote `View Task` from the page unless it truly opens a distinct task surface
  - shrink page-local task state to concise tags or short inline metadata
  - move task switching and deeper task inspection into `Global Context`
  - keep `SimulationResultExplorer` as the visual primary surface

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

1. `LM1` final `Save to Design` model
2. `LM2` simulation task-surface cleanup in the same area
3. `LM3` raw-data continuity + copy truthfulness
4. `LM4` characterization submission contract and runnable workflow
5. `LM5` first basic analysis path
6. `LM6` Local Mode end-to-end verification

## 8) Immediate Next Implementation Recommendation

- The next implementation should be `LM1 + LM2` together.
- Reason:
  - they unblock the simulation-to-design ownership model
  - they reduce page noise immediately
  - they avoid merging a half-correct save UX that the user already rejected
- Concrete target for the next frontend/backend pair:
  - backend: explicit create-design contract
  - frontend simulation: dropdown + `New Design` dialog + lighter task presentation

## 9) Notes On Existing Reviewed Frontend Delivery

- Reviewed commit:
  - `7e815bac29e6de513e17fe525419a6954232a767`
- Current judgement:
  - useful reference for trace-summary cleanup
  - useful reference for moving away from `Save to Dataset`
  - not ready to merge as the final save-target solution because it still leaves new-design creation on a free-text path

## 10) Verification Commands

- Frontend:
  - `npm run typecheck --prefix frontend`
  - `npm run test --prefix frontend`
- Backend:
  - `cd backend && uv run pytest -q`
  - `cd backend && uv run ruff check`
