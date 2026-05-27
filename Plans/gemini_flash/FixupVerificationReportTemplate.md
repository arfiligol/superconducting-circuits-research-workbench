# Fixup Verification Report: HFSS Layout Simulation Ingestion

This is the template the Gemini fixup agent should copy/create as
`Plans/gemini_flash/FixupVerificationReport.md` inside the assigned feature worktree.

## 1. Preflight

- Agent/model:
- Branch:
- Worktree:
- Starting status:
- Untracked scratch files removed:
- Root worktree report ignored as authoritative implementation report: yes/no

## 2. Findings Resolved

- Finding 1 undefined `np` in rewrite path:
  - files changed:
  - test evidence:
- Finding 2 durable pseudo-code:
  - files changed:
  - test evidence:
- Finding 3 dead multi-sweep branch:
  - files changed:
  - test evidence:
- Finding 4 scalar CSV unit regression:
  - files changed:
  - test evidence:

## 3. Backend Payload Evidence

- ND payload kind:
- Axis order:
- Axis values:
- TraceStore shape:
- Imaginary complex packing sample:
- `available_sweep_axes`:
- Characterization eligibility:

## 4. Commands

- `git diff --check`
  - result:
- `cd backend && uv run ruff check src/app/infrastructure/durable_catalog_repository.py src/app/infrastructure/rewrite_catalog_repository.py src/app/infrastructure/persisted_characterization_runtime.py`
  - result:
- Backend targeted tests:
  - command:
  - result:
- `npm run typecheck --prefix frontend`
  - result:
- `npm run test --prefix frontend -- data-browser.test.ts`
  - result:
- Optional full checks:
  - command:
  - result:

## 5. Final Status

- Commit hash:
- Remaining dirty files:
- Remaining untracked files:
- Known risks:
