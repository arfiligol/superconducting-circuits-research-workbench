# Simulation Result Task Surface Follow-ups

This file records user-validated UX issues discovered while frontend implementation is still in progress.
It is a planning note only and must not override `docs/reference/**`.

## Topic

- Area: `Simulation Result` task surfaces
- Status: `Partially resolved on main`
- Recorded: `2026-03-19`

## Confirmed Issues

### 1. `View Task` was semantically broken and is now removed from `main`

- The previous page-local CTA labeled `View Task` only reattached the selected task and could appear broken.
- `main` now removes that misleading wording and uses truth-based attach state instead.
- Remaining direction:
  - if the product later needs real task inspection, it should live in `Global Context`, not return as a misleading page-local CTA.

### 2. Simulation task information density is improved, but not fully settled

- `main` no longer shows the previous `Attached Run / Result Availability / Downstream State` wall.
- This materially improves the workflow hierarchy and keeps the explorer/result surfaces primary.
- Remaining direction:
  - continue shrinking non-essential page-local task state
  - let `Global Context` own deeper task browsing, switching, and inspection
  - avoid rebuilding a second task dashboard inside the workflow page

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

### 4. `Save to Design` now uses the correct explicit design-target model on `main`

- `main` now uses:
  - explicit design dropdown
  - `New Design` dialog
  - immediate create-and-select behavior
  - publish by explicit `design_id`
- Remaining direction:
  - if this pattern is reused in `Characterization`, prefer extracting shared primitives instead of reintroducing free-text target entry.

## Follow-up Direction

- Remove or demote misleading page-local task CTAs.
- Shrink simulation task state on the page to the minimum needed to keep the workflow legible.
- Keep explorer and result surfaces primary.
- Let `Global Context` own task browsing, task switching, and deeper task inspection.
- Reuse the merged explicit design selection / creation pattern where later workflow pages need it.

## Related Review Note

- The current frontend delivery for raw-data trace summaries changed the raw-data search placeholder to mention `source` and `trace ID`.
- Current backend search still filters by `parameter` and `provenance_summary` only.
- This mismatch should be corrected in a future frontend follow-up unless backend search scope is widened.
