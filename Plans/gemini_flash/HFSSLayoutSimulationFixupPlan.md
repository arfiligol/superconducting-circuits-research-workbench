# Plan Artifact v1: HFSS Layout Simulation Ingestion Fixup

Date: 2026-04-29
Status: Ready for Gemini 3 Flash fixup
Target agent: Gemini 3 Flash
Prompt level: L1 Fixup
Base worktree:
`/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/hfss-layout-simulation-ingestion-characterization`

## 1. Current review result

The first Gemini implementation is not mergeable.

Observed state:
- Worktree has uncommitted code changes.
- No commit hash was produced.
- `Plans/gemini_flash/VerificationReport.md` was filled in the root worktree, not in the
  assigned implementation worktree.
- The report is incomplete and inaccurate:
  - command result fields are empty;
  - it claims C4/C5 verification without formal evidence;
  - it claims shapes/payload details not proven by tests;
  - it says delivery report includes the report path, but no delivery report/commit exists.
- `backend/verify_hfss_ingestion.py` is an untracked ad-hoc script with a hardcoded local
  absolute worktree path. It must not be committed.
- `git diff --check` fails.
- Backend ruff fails.

This fixup must repair the existing feature worktree. Do not restart the milestone or
expand scope.

## 2. Review findings to resolve

### Finding 1: undefined `np` in rewrite nd_grid path

File:
`backend/src/app/infrastructure/rewrite_catalog_repository.py`

Problem:
- The new `nd_grid` branch uses `np.asarray` and `np.number` without importing numpy.
- `ruff` fails and runtime rewrite/local ingestion would raise `NameError`.

Required outcome:
- Rewrite/local `nd_grid` handling must run without `NameError`.
- Prefer avoiding numpy in this in-memory editable payload helper unless it is already an
  accepted module dependency in this file.
- Add or update a formal backend test that exercises rewrite/local raw ingestion of an
  `nd_grid` payload.

### Finding 2: unfinished pseudo-code in durable ND materializer

File:
`backend/src/app/infrastructure/durable_catalog_repository.py`

Problem:
- The ND materializer contains unused variables, a `for` loop with only `pass`, and comments
  explaining uncertainty about how to reconstruct axis values.
- `ruff` fails.
- This is not production code.

Required outcome:
- Remove all unfinished pseudo-code and uncertainty comments.
- Materialize `preview_payload.kind == "nd_grid"` through a deterministic path.
- Preserve axis order and values from the `nd_grid` payload.
- Use `write_nd_complex_trace_payload(...)` for ND payloads.
- Keep existing 1D `sampled_series` behavior working.
- Add or update formal backend tests proving ND shape, axis values, and representation-aware
  complex packing.

Implementation guidance:
- Do not flatten `nd_grid` into `series_table` before durable materialization unless you keep
  enough structured information to reconstruct all axes exactly.
- A cleaner approach is to let `_numeric_payload_from_preview_payload(...)` return an internal
  payload with `kind == "nd_grid"`, `axes`, and `values`, then let
  `_materialize_trace_payload(...)` write that directly.
- `_numeric_payload_axis_lengths(...)`, `_axes_with_numeric_payload(...)`, and coordinate
  digest helpers must not collapse `frequency x L_jun` to a single flattened row count.
- For `representation == "imaginary"`, scalar values must be stored as imaginary complex
  values. If this is not true, Characterization will read zeros via `np.imag(...)`.

### Finding 3: dead multi-sweep branch in characterization runtime

File:
`backend/src/app/infrastructure/persisted_characterization_runtime.py`

Problem:
- A new `len(sweep_axes) > 1` branch was inserted after an unconditional raise for the same
  condition, so it is unreachable.
- It also adds trailing whitespace.
- Multi-sweep flattening was not part of this fixup.

Required outcome:
- Remove the unreachable branch and trailing whitespace.
- Keep the existing "at most one non-frequency sweep axis" Characterization contract.
- Do not implement composite multi-axis sweep support in this slice.

### Finding 4: frontend sweep detection breaks 1D scalar CSVs with units

File:
`frontend/src/features/data-browser/lib/upload-first-ingestion.ts`

Problem:
- Any non-frequency column with a unit suffix such as `Y11 [S]` can be misclassified as a
  sweep column.
- A normal 1D CSV like `Freq [GHz],Y11 [S]` would lose its only data column and fail.

Required outcome:
- Sweep detection must only activate when there is a separate data column.
- For this milestone, it is acceptable to limit HFSS sweep detection to the 3-column layout:
  one sweep column, one frequency column, one data column.
- Add a frontend regression test for `Freq [GHz],Y11 [S]` proving it remains a 1D scalar
  upload.
- Keep the existing HFSS 3-column parser test.

## 3. Additional required cleanup

- Delete `backend/verify_hfss_ingestion.py` from the feature worktree. It is an untracked
  scratch script with hardcoded local paths.
- Create and fill a new report inside the feature worktree:
  `Plans/gemini_flash/FixupVerificationReport.md`
- Do not edit the root worktree report as the authoritative implementation report.
- Commit the fixed work on branch
  `codex/hfss-layout-simulation-ingestion-characterization`.

## 4. Allowed area

- `frontend/src/features/data-browser/lib/upload-first-ingestion.ts`
- `frontend/tests/data-browser.test.ts`
- `backend/src/app/infrastructure/durable_catalog_repository.py`
- `backend/src/app/infrastructure/rewrite_catalog_repository.py`
- `backend/src/app/infrastructure/persisted_characterization_runtime.py`
- `backend/tests/**` only for directly relevant ingestion/characterization tests
- `tests/core/shared/persistence/**` only if an existing layout-ingest test is the right
  target
- `Plans/gemini_flash/FixupVerificationReport.md`

## 5. Do not touch

- `data/raw/**` except read-only smoke input.
- Legacy NiceGUI.
- Simulation page/workflow.
- Publication repositories.
- Unrelated formatting or repo-wide ruff fixes.
- OpenAPI artifacts unless an API response schema actually changes.
- Root worktree files outside the assigned feature worktree.

## 6. Verification requirements

Minimum checks:
- `git diff --check`
- `cd backend && uv run ruff check src/app/infrastructure/durable_catalog_repository.py src/app/infrastructure/rewrite_catalog_repository.py src/app/infrastructure/persisted_characterization_runtime.py`
- Backend targeted tests that cover:
  - rewrite/local `nd_grid` ingestion metadata;
  - durable `nd_grid` materialization or helper readback;
  - imaginary representation complex packing;
  - Characterization eligibility for `[frequency, L_jun]`.
- `npm run typecheck --prefix frontend`
- `npm run test --prefix frontend -- data-browser.test.ts`

Recommended if time allows:
- `cd backend && uv run pytest -q <specific touched test files>`
- `npm run test --prefix frontend`

Report exact commands and results in `Plans/gemini_flash/FixupVerificationReport.md`.

## 7. Acceptance criteria

This fixup is acceptable only if:
- The feature branch has a commit.
- The worktree has no untracked scratch scripts.
- `git diff --check` passes.
- Backend ruff passes for touched backend files.
- Formal tests cover the fixed backend behavior.
- The frontend scalar-with-unit regression passes.
- `FixupVerificationReport.md` exists in the feature worktree and contains concrete command
  results.
