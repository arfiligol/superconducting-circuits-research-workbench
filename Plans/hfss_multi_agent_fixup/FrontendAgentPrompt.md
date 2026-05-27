# Frontend Agent Prompt: HFSS Upload Parser Fixup

```text
Task ID / Topic:
HFSS layout simulation upload-first parser fixup.

Agent Lane:
Frontend Agent.

Prompt Level:
L1 Fixup.

Branch / Worktree:
Create a clean isolated branch/worktree from `develop`:
- Branch: `codex/hfss-ingestion-frontend-fixup`
- Worktree: `/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/hfss-ingestion-frontend-fixup`

Do not edit this rejected dirty prototype worktree:
`/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/hfss-layout-simulation-ingestion-characterization`

You may read its diff as reference only.

Read First:
1. `AGENTS.md`
2. `docs/reference/guardrails/_agent_catalog.yml`
3. `docs/reference/guardrails/project-basics/index.md`
4. `docs/reference/guardrails/ui-ux-quality/index.md`
5. `docs/reference/guardrails/code-quality/data-handling.md`
6. `docs/reference/guardrails/execution-verification/branch-and-worktree-flow.md`
7. `docs/reference/guardrails/execution-verification/contributor-reporting.md`
8. `/Users/arfiligol/Github/superconducting-circuits-tutorial/Plans/hfss_multi_agent_fixup/MultiAgentFixupPlan.md`

Current Problem:
The previous single-agent implementation was rejected. The frontend defect was:
- sweep-column detection treated any non-frequency column with a `[unit]` suffix as a sweep column, so a normal scalar CSV such as `Freq [GHz],Y11 [S]` could lose its only data column and fail.

Goal:
Implement the frontend upload-first parser support for HFSS CSVs while preserving existing scalar CSV behavior.

Allowed Area:
- `frontend/src/features/data-browser/lib/upload-first-ingestion.ts`
- `frontend/tests/data-browser.test.ts`

Do Not Touch:
- `backend/**`
- `data/raw/**` except read-only inspection
- legacy NiceGUI
- Simulation page/workflow
- broad UI redesign/styling
- root `Plans/**` unless explicitly asked by Planning & Reviewing Agent
- the rejected dirty prototype worktree except read-only reference

Required Outcome:
1. Existing 1D upload behavior remains compatible.
2. `Freq [GHz],Y11 [S]` remains a valid 1D scalar upload, not a sweep.
3. HFSS 3-column sweep CSV is supported:
   - sweep column like `L_jun [nH]`;
   - frequency column like `Freq [GHz]`;
   - data column like `im(Yt(...)) []`.
4. For 3-column HFSS sweep files, emit canonical axes:
   - first axis: `{ name: "frequency", unit: "GHz", length: frequency_count }`
   - second axis: `{ name: "L_jun", unit: "nH", length: sweep_count }`
5. For 3-column HFSS sweep files, emit `preview_payload.kind == "nd_grid"` with:
   - axis values in `[frequency, L_jun]` order;
   - values shaped `[frequency_index][sweep_index]`.
6. Metadata inference supports:
   - `im(Yt(...))` -> `family: "y_matrix"`, `representation: "imaginary"`;
   - `re(Yt(...))` -> `family: "y_matrix"`, `representation: "real"`;
   - `im(St(...))` -> `family: "s_matrix"`, `representation: "imaginary"`;
   - `re(St(...))` -> `family: "s_matrix"`, `representation: "real"`;
   - `ang_rad(St(...))` -> `representation: "phase"`;
   - Yin formula with filename `*_Re_Yin.csv` -> `family: "y_matrix"`, `parameter: "Yin"`, `representation: "real"`.
7. Filename fallback supplies parameters like `Y11`, `S21`, `Yin` when the HFSS formula header does not expose them.
8. Sweep detection should be conservative. For this fixup, it may be limited to exactly the 3-column layout: one sweep-like column, one frequency column, one data column.

Verification:
Run and report exact results.

Required:
- `git diff --check`
- `npm run typecheck --prefix frontend`
- `npm run test --prefix frontend -- data-browser.test.ts`

Test coverage must include:
- existing scalar upload behavior;
- scalar-with-unit regression: `Freq [GHz],Y11 [S]`;
- HFSS 3-column `L_jun/Freq/im(Yt(...))` emits `nd_grid`;
- HFSS Yin 2-column formula/filename inference.

Recommended:
- `npm run test --prefix frontend`

Handoff:
Commit on `codex/hfss-ingestion-frontend-fixup`.
Return Delivery Report v1 with:
- commit hash;
- changed files and reasons;
- how the frontend finding was resolved;
- exact verification commands/results;
- known risks;
- explicit statement that the rejected Gemini worktree was not edited.
```
