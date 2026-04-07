# Circuit Schemdraw Guidance And Preview Export Plan

This file is an execution plan for the Schemdraw page enhancement.
It does not replace `docs/reference/**`.
The owner contracts remain in the accepted docs SoT; this file exists to drive planning, prompt-writing, and review order.

## 0) Task Information

- Agent: `Planning Agent`
- Task ID / Topic: `M9-Circuit-Schemdraw-Guidance-And-Preview-Export`
- Status: `Ready for docs-first planning 2026-03-30`

## 1) Goal

Implement two user-facing improvements on `/circuit-schemdraw`:

1. add one in-page guidance card that briefly explains how to write Schemdraw source on this page in a way that:
   - satisfies the page/backend contract
   - stays structurally readable to AI
   - stays readable to humans editing the same source later
2. add a `Download` action to the live preview surface so the latest rendered preview can be downloaded as:
   - `SVG`
   - `PNG`

The immediate success condition is:

1. the page itself gives compact, trustworthy guidance for Schemdraw authoring
2. the guidance does not turn the page into a documentation wall
3. the live preview can be downloaded from a single explicit user action
4. the export behavior remains truthful to the current render authority and stale-preview rules

## 2) Current State

Current accepted SoT already defines:

- `/circuit-schemdraw` is an editor-assist page, not a task workflow
- backend owns authoritative syntax validation and live preview
- the page hierarchy is:
  - linked schema context
  - source editor + SVG live preview
  - backend diagnostics
  - linked schema snapshot
- the backend render contract currently returns:
  - `svg`
  - structured diagnostics
  - preview metadata such as width / height / viewBox

Current gaps:

- the page does not yet provide a compact, explicit authoring guide card
- the live preview does not yet expose an explicit download UX for `SVG` / `PNG`
- the contract does not yet clearly say whether preview export is:
  - frontend-derived from the authoritative SVG payload
  - or backend-assisted via additional export semantics

## 3) Source Of Truth

Primary owner docs:

- `docs/reference/app/frontend/research-workflow/schemdraw.md`
- `docs/reference/app/backend/schemdraw-render.md`
- `docs/reference/guardrails/ui-ux-quality/component-guidelines.md`
- `docs/reference/guardrails/project-basics/source-of-truth-order.md`

Supporting context:

- `docs/how-to/contributing/circuit-diagrams.md`
- `frontend/src/features/circuit-schemdraw/components/circuit-schemdraw-workspace.tsx`
- `frontend/src/features/circuit-schemdraw/lib/api.ts`
- `frontend/tests/circuit-schemdraw.test.ts`

## 4) Planning Rule For This Workstream

This workstream should stay docs-first.

- freeze the product / contract intent first
- only then decide whether a backend implementation slice is actually required
- do not manufacture backend work if the accepted contract shows that frontend can safely derive export from the current authoritative SVG response

Implementation slices can remain broad inside their lane, but ownership must stay clear:

- page guidance and visible controls belong to frontend/page SoT
- render/export authority and payload semantics belong to backend render SoT

## 5) Design Direction To Freeze

### A. Guidance card should be compact and task-serving

The new card should:

- sit naturally inside the Schemdraw workspace, not above or below the whole page as a large explanation wall
- explain only the authoring rules needed to succeed on this page
- explicitly help both:
  - human editing
  - AI-assisted editing

It should likely cover:

- required source shape or entrypoint expectations
- readable import / naming / structure expectations
- avoiding opaque or overly magical source that backend can execute but humans/AI cannot reliably inspect
- the fact that backend remains the render / syntax authority

### B. Download UX should stay explicit and simple

The page should expose:

- one `Download` button in the live preview area
- one dialog that lets the user choose `SVG` or `PNG`

The UX should avoid:

- multiple always-visible export buttons cluttering the preview header
- hidden export affordances buried in diagnostics or viewer chrome

### C. Export ownership must be truthful

The docs-first pass must settle:

- whether `SVG` download is simply the authoritative backend SVG response saved as a file
- whether `PNG` is derived on the frontend from that SVG
- or whether backend must provide additional export-specific support

Default planning assumption:

- current backend render response likely already gives enough authority for frontend-side `SVG` export
- current backend render response may also be sufficient for frontend-side `PNG` derivation
- backend slice should only be opened if the docs/contract review concludes the current response is insufficient or ambiguous

## 6) Implementation Milestones

### Milestone A: Document Context / Contract Freeze

- Prompt level:
  - `L2 Slice`
- Goal:
  - update owner docs so this page formally owns:
    - compact authoring guidance card behavior
    - download action + dialog behavior
    - truthful export ownership
- Allowed Area:
  - `docs/reference/app/frontend/research-workflow/schemdraw.md`
  - `docs/reference/app/backend/schemdraw-render.md`
  - supporting docs only if alignment is needed
- Required outcome:
  - page spec explicitly allows and constrains the new guidance card
  - page spec explicitly allows and constrains download UX
  - backend render docs clarify whether preview export is frontend-derived or needs backend support
  - no SoT drift between page spec and render contract

### Milestone B: Backend Slice, If Contract Support Is Needed

- Prompt level:
  - `L1 Fixup` or `L2 Slice`, depending on what the docs freeze decides
- Goal:
  - implement only the backend contract support required by the accepted docs
- Allowed Area:
  - `backend/**`
  - `core/**` only if shared render/export helpers are genuinely needed
- Do Not Touch:
  - `frontend/**`
  - unrelated circuit-definition or task-flow work
- Required outcome:
  - render/export payload semantics become explicit and stable if the current backend envelope is insufficient
  - no task/persistence workflow is introduced
  - no hidden file-save backend side effect is introduced

### Milestone C: Frontend Adoption

- Prompt level:
  - `L3 Milestone`
- Goal:
  - add the guidance card and preview download UX to `/circuit-schemdraw`
- Allowed Area:
  - `frontend/src/features/circuit-schemdraw/**`
  - `frontend/tests/**`
- Do Not Touch:
  - unrelated simulation or characterization surfaces
  - docs unless explicit sync is requested later
- Required outcome:
  - guidance card is visible and compact
  - live preview has one `Download` button
  - dialog offers `SVG` and `PNG`
  - export behavior follows the accepted ownership contract
  - stale preview / latest-only apply behavior remains intact

### Milestone D: Browser Verification And Fixup Loop

- Prompt level:
  - `L1 Fixup` or `L2 Slice`, depending on what remains
- Goal:
  - verify the real page behavior at `/circuit-schemdraw`
- Required outcome:
  - download affordance is visible and understandable
  - generated files open correctly as `SVG` / `PNG`
  - guidance card does not crowd out the editor / preview

## 7) Non-Goals

- no redesign of the whole Schemdraw page hierarchy
- no migration of Schemdraw into task queue / persisted execution flow
- no large tutorial wall embedded into the page body
- no expansion into a generalized asset export center
- no assumption that backend must own PNG generation unless the docs freeze explicitly requires it

## 8) Verification Matrix

### Docs

- `uv run python scripts/check_docs_nav_routes.py --check-source`
- `./scripts/prepare_docs_locales.sh`
- `uv run --group dev zensical build -f zensical.toml`
- `./scripts/build_docs_sites.sh`
- `uv run python scripts/check_docs_nav_routes.py --check-built`

### Frontend

- `npm install --prefix frontend`
- `npm run typecheck --prefix frontend`
- `npm run test --prefix frontend -- circuit-schemdraw.test.ts`
- `npm run test --prefix frontend -- workspace-shell.test.ts`

### Browser / UI

- open `/circuit-schemdraw`
- verify the guidance card is present and concise
- verify the `Download` button opens a dialog
- verify both `SVG` and `PNG` export paths work
- verify the live preview still respects stale/latest render semantics

### Backend

Only if Milestone B is opened:

- `cd backend && uv run ruff check`
- `cd backend && uv run pytest -q`

## 9) Review Focus

Each delivery report in this workstream should be reviewed against:

- whether the guidance card stays compact and page-serving
- whether the page still centers editor + preview rather than support surfaces
- whether export ownership is truthful to the accepted render contract
- whether `PNG` behavior is implemented in the lane that actually owns it
- whether no accidental task/persistence workflow was introduced

## 10) Recommendation

The most likely good path is:

1. freeze the contract in docs
2. decide whether backend changes are actually required
3. if backend changes are not required, go directly to a frontend implementation slice
4. if backend changes are required, keep them narrow and contract-driven before frontend adoption
