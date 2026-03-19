# Simulation Result Task Surface Follow-ups

This file records user-validated UX issues discovered while frontend implementation is still in progress.
It is a planning note only and must not override `docs/reference/**`.

## Topic

- Area: `Simulation Result` task surfaces
- Status: `Active follow-up`
- Recorded: `2026-03-19`

## Confirmed Issues

### 1. `View Task` is semantically broken on the page

- Current implementation in [simulation-workbench-shell.tsx](/Users/arfiligol/Github/superconducting-circuits-tutorial/frontend/src/features/simulation/components/simulation-workbench-shell.tsx#L849) labels the CTA as `View Task`.
- The handler only calls `attachTask(taskId)` in [simulation-workbench-shell.tsx](/Users/arfiligol/Github/superconducting-circuits-tutorial/frontend/src/features/simulation/components/simulation-workbench-shell.tsx#L1863), so it does not open a distinct task surface.
- When the current task is already attached, the button can appear to do nothing.
- Planning judgement:
  - `View Task` should not remain as a page-local label if it only rebinds the current task selection.
  - Preferred direction is either:
    - remove it from the page, or
    - move true task inspection to `Global Context` and rename any page-local action accordingly.

### 2. Simulation task information density is still too high

- The page currently repeats task-oriented information across:
  - stage notice actions
  - attached/latest run cards
  - `Attached Run / Result Availability / Downstream State` summary cards
  - persisted result support disclosure
- The densest block is in [simulation-workbench-shell.tsx](/Users/arfiligol/Github/superconducting-circuits-tutorial/frontend/src/features/simulation/components/simulation-workbench-shell.tsx#L2879).
- User direction is explicit:
  - reduce or remove page-local task cards
  - keep workflow surfaces clean
  - move non-essential task detail into `Global Context`
- Planning judgement:
  - `Simulation Result` should stay result-first, not task-first.
  - Page-local task presentation should collapse to minimal state, ideally tag-level or short inline metadata only.
  - If deeper task diagnostics are needed, they belong in `Global Context`.

### 3. `Global Context` task selection is a valid target model

- Desired behavior:
  - user chooses which task to inspect in `Global Context`
  - the selected compatible task is reflected in `Simulation Result`
- Planning judgement:
  - This direction is feasible and aligns with existing UX principles.
  - The main constraint is context compatibility:
    - selected task must still match current workspace visibility
    - selected task must remain compatible with the current definition/dataset context
  - Best adoption path is to reuse the existing page selection authority rather than inventing a second parallel state model.
    - likely candidate: current `taskId` search-param binding already used by the page
- Design risks to handle explicitly:
  - if `Global Context` selects an incompatible task, the page must show a concise mismatch state instead of a diagnostics wall
  - the page must still have a clear fallback when no explicit task is selected, most likely the latest compatible run
  - post-processing unlock state must follow the selected upstream simulation task consistently

### 4. `Save to Design` still needs an explicit design creation flow

- Current `main` branch still uses a free-text publication target model.
- The reviewed frontend save-UX slice moves in the right direction, but its `New design` path still relies on typing a name.
- Latest user direction is stricter:
  - save target should be an explicit design dropdown
  - new design creation should happen through a button + dialog
  - once created, the new design should appear in the dropdown immediately
  - avoid typo-prone free-text naming in the main save surface
- Planning judgement:
  - the final save-target UX should not ship as segmented `Existing / New` plus free text
  - this likely requires a dataset-scoped create-design mutation or equivalent explicit create flow, not only the current implicit publish-by-name behavior

## Follow-up Direction

- Remove or demote misleading page-local task CTAs.
- Shrink simulation task state on the page to the minimum needed to keep the workflow legible.
- Keep explorer and result surfaces primary.
- Let `Global Context` own task browsing, task switching, and deeper task inspection.
- Finalize simulation publication around explicit design selection and explicit design creation.

## Related Review Note

- The current frontend delivery for raw-data trace summaries changed the raw-data search placeholder to mention `source` and `trace ID`.
- Current backend search still filters by `parameter` and `provenance_summary` only.
- This mismatch should be corrected in a future frontend follow-up unless backend search scope is widened.
