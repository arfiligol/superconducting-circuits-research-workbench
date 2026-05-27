# Implementation Prompt: HFSS Layout Simulation Ingestion to Characterization

Use this prompt with Gemini 3 Flash.

```text
Task ID / Topic:
HFSS layout simulation ingestion to Characterization run-through.

Prompt Level:
L3 Milestone.

Model:
Gemini 3 Flash. Use precise, direct execution. Do not improvise architecture beyond the plan.

Base:
Work from `develop` at or after commit `4103aa2c17715b8c717ac371ecddd08128100f8a`.
If the base is older, stop and report.

Branch / Worktree:
Create and use a dedicated branch and isolated worktree:
- Branch: `codex/hfss-layout-simulation-ingestion-characterization`
- Worktree: `/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/hfss-layout-simulation-ingestion-characterization`

Read First:
1. `AGENTS.md`
2. `docs/reference/guardrails/_agent_catalog.yml`
3. `docs/reference/guardrails/project-basics/index.md`
4. `docs/reference/guardrails/code-quality/data-handling.md`
5. `docs/reference/guardrails/execution-verification/index.md`
6. `docs/reference/guardrails/execution-verification/branch-and-worktree-flow.md`
7. `docs/reference/guardrails/execution-verification/contributor-reporting.md`
8. `Plans/gemini_flash/HFSSLayoutSimulationIngestionPlan.md`
9. `Plans/gemini_flash/VerificationReport.md`

Current State:
- The frontend upload-first parser currently handles 1D frequency series.
- HFSS files include 3-column sweep CSVs such as `L_jun [nH]`, `Freq [GHz]`, `im(Yt(...)) []`.
- HFSS files also include 2-column formula CSVs such as `Freq [GHz]`, Yin formula.
- Durable backend ingestion already builds structure summaries but currently materializes uploaded preview data as 1D payloads.
- Rewrite/local ingestion does not enrich raw ingestion summaries in the ingest path.
- Characterization can consume ND TraceStore payloads with `frequency` plus at most one sweep axis if they are materialized correctly.

Goal:
Implement the plan in `Plans/gemini_flash/HFSSLayoutSimulationIngestionPlan.md` so an ANSYS HFSS layout simulation CSV can be uploaded, ingested as a truthful canonical trace, browsed as ND when applicable, selected as eligible for `admittance_extraction`, and used by Characterization extraction.

Allowed Area:
- `frontend/src/features/data-browser/**`
- `frontend/tests/**` only for directly relevant data-browser ingestion tests
- `backend/src/app/domain/**` only if needed for existing contracts/tests
- `backend/src/app/infrastructure/durable_catalog_repository.py`
- `backend/src/app/infrastructure/rewrite_catalog_repository.py`
- `backend/src/app/infrastructure/persisted_runtime.py` only for small TraceStore write helper changes
- `backend/src/app/infrastructure/persisted_characterization_runtime.py` only if tests prove a narrow compatibility fix is required
- `backend/tests/**` only for directly relevant ingestion/characterization tests
- `tests/core/shared/persistence/**` only for existing layout trace ingest coverage if relevant
- `Plans/gemini_flash/VerificationReport.md`

Do Not Touch:
- `data/raw/**` except read-only smoke input
- legacy NiceGUI files
- unrelated Simulation page/workflow files
- publication repositories
- docs outside `Plans/gemini_flash/**`
- broad styling/UI redesign
- schema migration files unless you stop and ask first

Implementation Requirements:
1. Follow every checkpoint C0-C5 in `Plans/gemini_flash/HFSSLayoutSimulationIngestionPlan.md`.
2. Preserve existing 1D upload behavior.
3. Add HFSS 3-column sweep parsing with canonical axes `[frequency, L_jun]`.
4. Add HFSS formula/header and filename fallback metadata inference.
5. Add backend support for `preview_payload.kind == "nd_grid"`.
6. Materialize ND grids to TraceStore/Zarr using the existing TraceStore abstraction.
7. Keep dense numeric payload out of long-term metadata/read model storage except necessary preview samples.
8. Implement representation-aware complex packing. In particular, `imaginary` values must be stored as imaginary complex values, not as real values.
9. Make rewrite/local raw ingestion summaries truthful by applying `build_trace_structure_summary(...)`.
10. Prove `layout_simulation` `y_matrix` `Y11` `imaginary` traces with `[frequency, L_jun]` are eligible for `admittance_extraction`.
11. Prove admittance extraction runs on a mini inline HFSS-style fixture and preserves `L_jun` as the member/input dimension.
12. Fill `Plans/gemini_flash/VerificationReport.md` as you work.

Non-Goals:
- No physical mode linking.
- No downstream `L_s + L_jun` fitting.
- No editable Collection CRUD.
- No folder/batch uploader unless trivial and fully tested.
- No raw data modifications.
- No new JSON-only numeric trace pipeline.

Verification:
Run and record results in `Plans/gemini_flash/VerificationReport.md`.

Required:
- `npm install --prefix frontend`
- `npm run typecheck --prefix frontend`
- `npm run test --prefix frontend -- data-browser.test.ts`
- `cd backend && uv run ruff check`
- Targeted backend tests you add/update for raw ingestion, ND TraceStore materialization, characterization eligibility, and admittance extraction.

Strongly preferred if time allows:
- `npm run test --prefix frontend`
- `cd backend && uv run pytest -q`
- `npm run openapi:check` only if API artifacts changed.

Real-data smoke:
If `data/raw/layout_simulation/PF6FQ/` exists, use it read-only. Record the exact file path and result. If real browser smoke is practical, include screenshot/text evidence. If the smoke is blocked by unrelated local runtime state, record the blocker precisely.

Stop Conditions:
Stop and report instead of guessing if:
- base commit is wrong;
- there are dirty changes outside your assigned worktree;
- a full HFSS grid cannot be safely transported through the current API path;
- TraceStore cannot write/read the ND shape;
- implementation would need schema migrations;
- real-data smoke requires modifying `data/raw`.

Handoff:
Commit your changes on the assigned branch and provide Delivery Report v1 with:
- assigned branch/worktree;
- commit hash;
- changed files with reasons;
- API/contract touched matrix;
- test commands and results;
- real-data smoke evidence or exact blocker;
- known risks;
- completed `Plans/gemini_flash/VerificationReport.md` path.
```
