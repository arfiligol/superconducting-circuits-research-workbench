# Local Mode Research Usability Sprint

This file is the remaining execution overlay for Local Mode research usability.
It does not replace `docs/reference/**`.
It exists only to track the still-open product work after the major simulation, post-processing, save-traces, characterization, UUID-identity, and workflow-test slices already landed on `main`.

## 0) Task Information

- Agent: `Planning Agent`
- Task ID / Topic: `L8-Local-Mode-Research-Usability`
- Status: `Active backlog cleanup 2026-03-24`

## 1) Goal

Reach a Local Mode workflow where one researcher can complete a truthful research loop without relying on Online Mode:

1. choose a circuit definition and run a simulation
2. browse simulation and post-processing results
3. save visible traces into a design inside the active dataset
4. open the saved traces in Raw Data
5. select the same design in Characterization
6. run a real analysis
7. reopen the persisted result after refresh and continue working

## 2) Already Landed On `main`

- worker-backed local runtime with queue-backed submit path
- simulation result explorer and post-processing result explorer
- `Save Traces` visible-trace publication model
- post-processing browse/source correction
- first runnable Local Mode characterization path: `admittance_extraction`
- backend integration coverage and frontend browser smoke coverage for the simulation workflow
- schema identity UUIDv4 cutover across backend, frontend, docs, and DB migration

## 3) Remaining Product Work

### LM3 Raw Data continuity and copy truthfulness

- Goal:
  make saved traces feel obvious and truthful once the user opens `Raw Data`.
- Still open:
  - ensure saved-trace continuity is easy to follow from `Circuit Simulation` into `Raw Data`
  - correct any UI copy that implies backend search/filter capability the backend does not actually support
  - keep the surface compact and browse-first

### LM6 Live Local Mode end-to-end verification

- Goal:
  prove the real Local Mode loop against the live backend/runtime, not only seeded or partial smoke paths.
- Still open:
  - live Redis + `sc-app` + workers browser-driven flow
  - submit simulation from the UI
  - wait for completion
  - submit post-processing from the UI
  - browse result
  - save traces
  - reopen in Raw Data
  - run Characterization and reopen persisted result

### LM7 Characterization durable tagging continuity

- Goal:
  ensure newly generated local characterization results preserve tagging/identify continuity after refresh and reopen.
- Still open:
  - verify newly created local results keep tagging state across persisted reload
  - confirm the behavior in real integrated flow, not only in-session state

### LM8 Next characterization analysis path

- Goal:
  expand beyond `admittance_extraction` with one additional research-useful runnable analysis.
- Still open:
  - choose the next analysis based on actual research value
  - keep unsupported analyses truthful instead of implying they are runnable

## 4) Non-blocking UX Follow-ups

- `Global Context` may later own deeper task browsing/switching for compatible simulation tasks.
- This is still a valid direction, but it is not the main blocker for the Local Mode research loop.

## 5) Recommended Execution Order

1. `LM3` Raw Data continuity and copy truthfulness
2. `LM6` live Local Mode end-to-end verification
3. `LM7` characterization durable tagging continuity
4. `LM8` next runnable characterization analysis

## 6) Exit Condition

This planning note can be retired once:

- the live Local Mode loop is browser-verified end to end
- Raw Data continuity is truthful and low-friction
- characterization tagging continuity for generated local results is verified
- the next characterization analysis path is either shipped or explicitly deprioritized
