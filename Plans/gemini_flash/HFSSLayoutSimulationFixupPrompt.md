# Fixup Prompt: HFSS Layout Simulation Ingestion

Use this prompt with Gemini 3 Flash.

```text
Task ID / Topic:
HFSS layout simulation ingestion fixup after review findings.

Prompt Level:
L1 Fixup. Do not restart the milestone. Repair the existing feature worktree.

Assigned Branch / Worktree:
- Branch: `codex/hfss-layout-simulation-ingestion-characterization`
- Worktree: `/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/hfss-layout-simulation-ingestion-characterization`

Read First:
1. `AGENTS.md`
2. `docs/reference/guardrails/_agent_catalog.yml`
3. `docs/reference/guardrails/project-basics/index.md`
4. `docs/reference/guardrails/code-quality/data-handling.md`
5. `docs/reference/guardrails/execution-verification/branch-and-worktree-flow.md`
6. `docs/reference/guardrails/execution-verification/contributor-reporting.md`
7. `/Users/arfiligol/Github/superconducting-circuits-tutorial/Plans/gemini_flash/HFSSLayoutSimulationFixupPlan.md`

Current Problem:
Your first implementation is not mergeable. It has uncommitted changes, no commit hash, no report in the assigned worktree, an untracked scratch script, `git diff --check` failures, and backend ruff failures.

Review Findings to Fix:
1. `backend/src/app/infrastructure/rewrite_catalog_repository.py`
   - The nd_grid path references `np` without importing it.
   - Fix runtime and ruff failure.
   - Add formal backend coverage for rewrite/local nd_grid ingestion.

2. `backend/src/app/infrastructure/durable_catalog_repository.py`
   - The ND materializer contains unfinished pseudo-code, unused variables, and a loop with only `pass`.
   - Replace it with deterministic production code.
   - Preserve nd_grid axis order and axis values.
   - Use TraceStore/Zarr via `write_nd_complex_trace_payload(...)`.
   - Do not collapse `frequency x L_jun` into a flattened 1D metadata shape.
   - Prove imaginary values are stored as imaginary complex values.

3. `backend/src/app/infrastructure/persisted_characterization_runtime.py`
   - Remove the unreachable multi-sweep branch added after the existing `len(sweep_axes) > 1` raise.
   - Remove trailing whitespace.
   - Do not implement multi-sweep flattening in this fixup.

4. `frontend/src/features/data-browser/lib/upload-first-ingestion.ts`
   - Fix sweep detection so a 1D scalar CSV with units, e.g. `Freq [GHz],Y11 [S]`, is not treated as a sweep.
   - For this milestone, HFSS sweep detection may be limited to the 3-column layout: one sweep column, one frequency column, one data column.
   - Add a frontend regression test for the scalar-with-unit case.

Required Cleanup:
- Delete the untracked scratch script `backend/verify_hfss_ingestion.py`.
- Create and fill `Plans/gemini_flash/FixupVerificationReport.md` inside the assigned feature worktree.
- Do not treat the root worktree's `Plans/gemini_flash/VerificationReport.md` as the implementation report.

Allowed Area:
- `frontend/src/features/data-browser/lib/upload-first-ingestion.ts`
- `frontend/tests/data-browser.test.ts`
- `backend/src/app/infrastructure/durable_catalog_repository.py`
- `backend/src/app/infrastructure/rewrite_catalog_repository.py`
- `backend/src/app/infrastructure/persisted_characterization_runtime.py`
- `backend/tests/**` only for directly relevant ingestion/characterization tests
- `tests/core/shared/persistence/**` only if an existing layout-ingest test is the right target
- `Plans/gemini_flash/FixupVerificationReport.md`

Do Not Touch:
- `data/raw/**` except read-only smoke input
- legacy NiceGUI
- Simulation page/workflow
- publication repositories
- unrelated formatting or repo-wide ruff fixes
- OpenAPI artifacts unless an API response schema actually changes
- root worktree files outside the assigned feature worktree

Verification:
Run and record exact results in `Plans/gemini_flash/FixupVerificationReport.md`.

Required:
- `git diff --check`
- `cd backend && uv run ruff check src/app/infrastructure/durable_catalog_repository.py src/app/infrastructure/rewrite_catalog_repository.py src/app/infrastructure/persisted_characterization_runtime.py`
- backend targeted tests covering rewrite/local nd_grid ingestion metadata, durable nd_grid materialization or helper readback, imaginary complex packing, and Characterization eligibility for `[frequency, L_jun]`
- `npm run typecheck --prefix frontend`
- `npm run test --prefix frontend -- data-browser.test.ts`

Recommended:
- `cd backend && uv run pytest -q <specific touched test files>`
- `npm run test --prefix frontend`

Handoff:
Commit the fixed changes on `codex/hfss-layout-simulation-ingestion-characterization` and provide Delivery Report v1 with:
- commit hash;
- changed files and reasons;
- how each review finding was resolved;
- exact verification commands and results;
- path to `Plans/gemini_flash/FixupVerificationReport.md`;
- known risks or blockers.
```
