# Backend Agent Prompt: HFSS Ingestion Backend Fixup

```text
Task ID / Topic:
HFSS layout simulation ingestion backend fixup.

Agent Lane:
Backend Agent.

Prompt Level:
L1 Fixup.

Branch / Worktree:
Create a clean isolated branch/worktree from `develop`:
- Branch: `codex/hfss-ingestion-backend-fixup`
- Worktree: `/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/hfss-ingestion-backend-fixup`

Do not edit this rejected dirty prototype worktree:
`/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/hfss-layout-simulation-ingestion-characterization`

You may read its diff as reference only.

Read First:
1. `AGENTS.md`
2. `docs/reference/guardrails/_agent_catalog.yml`
3. `docs/reference/guardrails/project-basics/index.md`
4. `docs/reference/guardrails/project-basics/backend-architecture.md`
5. `docs/reference/guardrails/code-quality/data-handling.md`
6. `docs/reference/guardrails/execution-verification/branch-and-worktree-flow.md`
7. `docs/reference/guardrails/execution-verification/contributor-reporting.md`
8. `/Users/arfiligol/Github/superconducting-circuits-tutorial/Plans/hfss_multi_agent_fixup/MultiAgentFixupPlan.md`

Current Problem:
The previous single-agent implementation was rejected. Backend defects were:
- rewrite/local nd_grid handling referenced undefined `np`;
- durable ND materialization contained unfinished pseudo-code and failed ruff;
- persisted characterization runtime added an unreachable multi-sweep branch after an existing raise.

Goal:
Implement the backend side correctly from clean `develop`, not by continuing the dirty rejected worktree.

Allowed Area:
- `backend/src/app/infrastructure/durable_catalog_repository.py`
- `backend/src/app/infrastructure/rewrite_catalog_repository.py`
- `backend/src/app/infrastructure/persisted_runtime.py` only if a small helper is required
- `backend/src/app/infrastructure/persisted_characterization_runtime.py` only if a narrow one-sweep compatibility fix is proven necessary
- `backend/src/app/domain/**` only if tests prove an existing domain contract needs a narrow adjustment
- `backend/tests/**` for directly relevant backend tests
- `tests/core/shared/persistence/**` only if an existing layout-ingest test is clearly the right target

Do Not Touch:
- `frontend/**`
- `data/raw/**` except read-only inspection
- legacy NiceGUI
- Simulation page/workflow
- publication repositories
- root `Plans/**` unless explicitly asked by Planning & Reviewing Agent
- OpenAPI artifacts unless a backend API schema actually changes
- the rejected dirty prototype worktree except read-only reference

Required Outcome:
1. Backend accepts upload trace drafts whose `preview_payload.kind` is `nd_grid`.
2. `nd_grid` axes and values are materialized to TraceStore/Zarr through existing TraceStore abstractions.
3. Dense ND values are not stored as the long-term metadata/read-model authority.
4. Axis order and axis values are preserved exactly from the payload, especially `[frequency, L_jun]`.
5. `frequency x L_jun` metadata remains truthful:
   - `ndim == 2`
   - `shape == (frequency_count, L_jun_count)`
   - `axes_summary.axis_names == ("frequency", "L_jun")`
   - `available_sweep_axes == ("L_jun",)`
6. Imaginary scalar uploads are packed as imaginary complex values, not real values.
7. Rewrite/local raw ingestion applies `build_trace_structure_summary(...)` in the ingest path.
8. Persisted characterization runtime keeps the current contract: at most one non-frequency sweep axis. Do not add composite multi-sweep flattening.
9. No unfinished comments, pass-only loops, unused variables, or ad-hoc scratch scripts.

Implementation Guidance:
- Prefer keeping an internal structured `nd_grid` payload until materialization, rather than flattening it into a lossy table before TraceStore write.
- If an editable preview helper needs a table, it may derive a summary/table from `nd_grid`, but that is not the TraceStore authority.
- Avoid introducing numpy into rewrite/local helper code unless the file already uses it and ruff/type checks stay clean.
- Use inline mini fixtures in tests. Do not depend on untracked `data/raw/**`.

Verification:
Run and report exact results.

Required:
- `git diff --check`
- `cd backend && uv run ruff check src/app/infrastructure/durable_catalog_repository.py src/app/infrastructure/rewrite_catalog_repository.py src/app/infrastructure/persisted_characterization_runtime.py`
- Targeted backend tests proving:
  - rewrite/local `nd_grid` ingestion metadata;
  - durable `nd_grid` materialization or helper readback;
  - imaginary complex packing;
  - characterization eligibility for a `[frequency, L_jun]` layout_simulation Y11 imaginary trace.

Recommended:
- `cd backend && uv run pytest -q <all touched backend test files>`

Handoff:
Commit on `codex/hfss-ingestion-backend-fixup`.
Return Delivery Report v1 with:
- commit hash;
- changed files and reasons;
- how each backend finding was resolved;
- exact verification commands/results;
- known risks;
- explicit statement that the rejected Gemini worktree was not edited.
```
