# Test Agent Prompt: HFSS Ingestion Integrated Verification

```text
Task ID / Topic:
HFSS layout simulation ingestion integrated verification.

Agent Lane:
Test Agent.

Prompt Level:
L1/L2 Test Fixup, depending on integrated scope.

Do not start until Planning & Reviewing Agent gives you an integration branch/worktree
that contains accepted Backend Agent and Frontend Agent commits.

Branch / Worktree:
Use only the integration branch/worktree assigned by Planning & Reviewing Agent.
Do not test against the rejected dirty Gemini prototype.

Read First:
1. `AGENTS.md`
2. `docs/reference/guardrails/_agent_catalog.yml`
3. `docs/reference/guardrails/code-quality/data-handling.md`
4. `docs/reference/guardrails/execution-verification/testing.md`
5. `docs/reference/guardrails/execution-verification/branch-and-worktree-flow.md`
6. `docs/reference/guardrails/execution-verification/contributor-reporting.md`
7. `/Users/arfiligol/Github/superconducting-circuits-tutorial/Plans/hfss_multi_agent_fixup/MultiAgentFixupPlan.md`

Goal:
Verify the integrated HFSS ingestion flow across frontend parser, backend ingestion, TraceStore materialization, and Characterization eligibility/extraction.

Allowed Area:
- Test files only, if missing integration coverage is required.
- Test fixtures only if small and not copied from `data/raw/**`.
- Output/evidence files only if Planning & Reviewing Agent explicitly asks.

Do Not Touch:
- Feature implementation code, unless Planning & Reviewing Agent explicitly asks for a tiny test-only compatibility fixture.
- `data/raw/**` except read-only smoke input.
- legacy NiceGUI.
- unrelated tests.

Required Scenarios:
1. Frontend parser:
   - scalar `Freq [GHz],Y11 [S]` remains 1D;
   - HFSS `L_jun/Freq/im(Yt(...))` emits `nd_grid`.
2. Backend ingestion:
   - `nd_grid` produces truthful metadata and TraceStore payload;
   - `available_sweep_axes == ("L_jun",)`;
   - imaginary values read back as imaginary component.
3. Characterization:
   - `layout_simulation` `y_matrix` `Y11` `imaginary` with axes `[frequency, L_jun]` is eligible for `admittance_extraction`;
   - extraction either completes on a mini inline fixture or reports a precise unrelated blocker.
4. Real-data smoke, if `data/raw/layout_simulation/PF6FQ/` exists:
   - read one representative file only;
   - do not modify raw data;
   - record exact file path and observed result.

Verification:
Run the checks assigned by Planning & Reviewing Agent. Minimum likely set:
- `git diff --check`
- `npm run typecheck --prefix frontend`
- `npm run test --prefix frontend -- data-browser.test.ts`
- `cd backend && uv run ruff check`
- targeted backend pytest files for ingestion/characterization

Handoff:
Return Test Report with:
- integration branch/worktree tested;
- commits under test;
- scenarios and evidence;
- exact commands/results;
- real-data smoke evidence or exact blocker;
- any remaining risks.
```
