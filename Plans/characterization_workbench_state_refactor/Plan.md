## Plan Artifact v1

### 0) 任務資訊
- Agent: Planning & Reviewing Agent
- Task ID / Topic: characterization-workbench-state-refactor
- 狀態: ready
- Lifecycle State: active
- Owner: Planning & Reviewing Agent
- Supersedes: none
- Retirement Criteria: delete-after-merge unless architecture decisions need promotion to
  `docs/reference/app/frontend/research-workflow/characterization.md`
- Cleanup Owner: Planning & Reviewing Agent

### 1) Goal
- 目標: 重構 `/characterization` page 的 state ownership 與 URL synchronization，
  不再用局部暫修處理 result flicker。
- 使用者成功條件:
  - 直接開啟指定 `datasetId + designId + resultId` 時，Result Preview 穩定停在
    requested result。
  - `taskId` 可以提供 active-run context，但不得覆寫明確指定的 `resultId`。
  - page 的資料流能被閱讀、測試與 debug；狀態 owner 清楚，不再靠多個 effect 互相修正。
  - Characterization workflow 保持既有功能：scope selection、data collection review、
    pipeline readiness、run submission、result list/detail、artifact explorer、identify/tagging。

### 2) Source of Truth
- Primary docs:
  - `docs/reference/app/frontend/research-workflow/characterization.md`
  - `docs/reference/app/backend/characterization-results.md`
  - `docs/reference/data-formats/dataset-record.md`
  - `docs/reference/guardrails/ui-ux-quality/state-management.md`
  - `docs/reference/guardrails/ui-ux-quality/routing.md`
  - `docs/reference/guardrails/ui-ux-quality/component-guidelines.md`
  - `docs/reference/guardrails/execution-verification/testing.md`
- Current authority owner:
  - Backend owns dataset/design/result truth.
  - Frontend owns page state projection, URL intent preservation, and user interaction state.
  - URL query params own shareable page intent.

### 3) Current Implementation State
- Existing code paths:
  - `frontend/src/features/characterization/components/characterization-workspace.tsx`
    is a large page component that renders the entire workbench and performs URL sync.
  - `frontend/src/features/characterization/hooks/use-characterization-workflow-data.ts`
    mixes route request hydration, active dataset/design resolution, task hydration, trace selection,
    analysis draft state, results list fallback, detail loading, mutations, and refresh logic.
  - `frontend/src/features/characterization/lib/workflow.ts`
    contains pure helpers, but current helpers do not model route intent as a separate authority.
  - `frontend/src/features/characterization/hooks/use-characterization-result-explorer.ts`
    separately manages artifact selection and payload fetches.
- Observed failure:
  - Opening
    `/characterization?datasetId=local-floatingqubit-100&taskId=490&designId=design_floatingqubitwithxy&resultId=char-admittance-run-24`
    eventually changes the selected result to `char-admittance-run-25`.
  - Backend verifies both run 24 and run 25 are valid results for the same design.
  - Task 490 points at analysis run 25, while the route explicitly asks for result 24.
- Root cause:
  - `requestedResultId`, `selectedResultId`, results-list fallback, task hydration, and URL replace
    are all allowed to write or derive the result selection.
  - When `selectedResultId` is temporarily cleared during design/dataset resolution, the results
    list fallback selects `rows[0]`, which is run 25.
  - `router.replace` then writes that derived fallback back into the URL, overwriting the user's
    explicit result intent.

### 4) Target Architecture

#### 4.1 State Ownership Layers

The frontend refactor should introduce explicit layers. Names may vary, but responsibilities must
remain separated.

1. Route Intent
   - Inputs: `datasetId`, `designId`, `resultId`, `taskId`, filters if present.
   - Source: `useSearchParams()`.
   - Semantics: user/shareable intent, not automatically invalid just because async data has not
     loaded.
   - Rule: route-provided `resultId` has priority over result-list fallback until backend proves it
     invalid for the resolved dataset/design.

2. Active Dataset Scope
   - Inputs: ActiveDataset provider state plus route `datasetId`.
   - Source: shell/session provider.
   - Rule: page must not delete or rewrite `datasetId` while route/session sync is unresolved.

3. Design Scope Resolution
   - Inputs: route requested design, active design rows.
   - Output: resolved design and recovery notice.
   - Rule: archived/deleted/stale design rebound is allowed, but it must explicitly invalidate
     dependent result intent only when the requested result cannot belong to the resolved design.

4. Task Context
   - Inputs: route `taskId`, latest characterization task, task detail.
   - Output: active run card context, optional pipeline draft hydration, optional result suggestion.
   - Rule: task context must not override an explicit route `resultId`.
   - Rule: if both `taskId` and `resultId` are present and they point at different valid results,
     Result Preview follows `resultId`; Active Analysis Run shows task context separately.

5. Pipeline Draft State
   - Inputs: selected traces, selected analysis, config values.
   - Scope: form/UI state only.
   - Rule: pipeline draft may hydrate from task only when there is no conflicting explicit route
     selection and the task belongs to the resolved design.

6. Result Selection
   - Inputs: route intent, user clicked result, task suggested result, result list.
   - Output: resolved result id for detail query.
   - Rule priority:
     1. Valid explicit route `resultId`
     2. User-selected result in current session
     3. Completed-run result after a submit in this page session
     4. Task handoff result only when no explicit route/user selection exists
     5. Results-list default
   - Rule: results-list default must never overwrite a still-valid explicit route result.

7. Result Detail Query
   - Inputs: dataset id, resolved design id, resolved result id.
   - Rule: a direct requested result may be detail-loaded even if the results list is empty or stale.
   - Rule: detail error should not immediately switch to list fallback unless the backend returns a
     scoped not-found/stale-design error and recovery rules say to rebound.

8. URL Sync
   - Inputs: canonical resolved route state.
   - Rule: URL sync is one-way and late. It should happen only after dataset/design/result hydration
     is stable enough to distinguish "not loaded yet" from "invalid".
   - Rule: preserve unrelated query params, especially `datasetId`.
   - Rule: do not write fallback result ids into URL while an explicit route `resultId` is pending
     validation.

#### 4.2 Suggested File Boundary

Frontend Agent may choose exact names, but the final code should be easier to reason about than the
current single hook/component.

- `frontend/src/features/characterization/lib/workflow.ts`
  - Keep pure selection/resolution functions here.
  - Add route-intent/result-selection helpers with unit coverage.
- `frontend/src/features/characterization/hooks/use-characterization-route-state.ts`
  - Parse route params.
  - Produce route intent and canonical URL sync intent.
  - No data fetching.
- `frontend/src/features/characterization/hooks/use-characterization-scope-data.ts`
  - Fetch active designs/traces/registry/history/results for resolved dataset/design.
  - No URL writes.
- `frontend/src/features/characterization/hooks/use-characterization-result-selection.ts`
  - Own result selection priority and detail query key.
  - Separate explicit route result from user-selected result.
- `frontend/src/features/characterization/hooks/use-characterization-pipeline-draft.ts`
  - Own analysis/config/trace selection draft.
- `frontend/src/features/characterization/components/*`
  - Extract Result Preview, Pipeline, Scope/Data Collection, and Active Run sections if useful.
  - Page component should compose sections and orchestrate high-level hook outputs.

This is a suggested boundary, not an `Allowed Files` constraint. The important requirement is clear
state ownership, not exact filenames.

### 5) Implementation Slice

#### Frontend
- Allowed Area:
  - `frontend/src/features/characterization/**`
  - `frontend/tests/characterization-workflow.test.ts`
  - Additional frontend tests if needed.
- Do Not Touch:
  - Backend APIs and data contracts unless a real contract mismatch is discovered.
  - Data ingestion, raw data, simulation pages except for shared type imports if unavoidable.
  - `data/**`, `.playwright-mcp/**`, and generated browser evidence.
- Goal:
  - Refactor Characterization page state architecture to remove selection loops and make
    URL-driven result preview deterministic.
  - Preserve existing visual language and workflow.
  - Add regression tests for route intent priority and task/result conflict behavior.

#### Backend
- No backend implementation slice for this plan.
- If frontend discovers backend ambiguity, stop and report it; do not invent frontend-only backend
  semantics.

#### Test
- Test Agent not required for the first implementation pass.
- Planning & Reviewing Agent must run a live browser smoke during merge review because this is a
  user-visible frontend workflow.

### 6) Test Backlog
- Unit / helper tests:
  - `requestedResultId=char-admittance-run-24` and result rows `[25, 24]` resolves to 24.
  - route `resultId` remains selected even if `taskId=490` points at run 25.
  - route result can be detail-loaded when result list is empty but the route result is present.
  - missing/stale route result rebounds only after backend/list evidence proves it unavailable.
  - design rebound invalidates result selection only when the requested result is not valid for the
    resolved design.
  - URL sync helper does not remove `datasetId`.
- Component/source tests:
  - Page URL sync is gated behind stable scope/result resolution.
  - Hook boundaries do not call `router.replace` from data-fetching hooks.
- Live smoke expected during merge review:
  - Open direct URL for run 24:
    `http://localhost:3000/characterization?datasetId=local-floatingqubit-100&taskId=490&designId=design_floatingqubitwithxy&resultId=char-admittance-run-24`
  - Wait through SWR/task refresh.
  - Confirm URL and Result Detail remain on `char-admittance-run-24`.
  - Confirm Active Analysis Run can still show task 490/run 25 context without switching Result
    Preview.

### 7) Verification Matrix
- Frontend:
  - `npm run typecheck --prefix frontend`
  - `npm run test --prefix frontend -- characterization-workflow.test.ts`
  - `npm run test --prefix frontend`
- Browser smoke:
  - Run local app with webpack dev script.
  - Capture screenshot or text evidence for direct run-24 URL stability.
- Optional focused root checks:
  - `git diff --check`

### 8) Risks / Open Decisions
- Task/result conflict UI:
  - If `taskId` points to run 25 and `resultId` points to run 24, the plan requires result preview
    to follow `resultId`. The UI may add a concise notice, but must not switch result selection.
- URL ownership:
  - If ActiveDataset provider currently removes `datasetId` after session sync, the Characterization
    page must not independently cause further loss of route intent.
- Scope of refactor:
  - This is intentionally broader than a one-line fix, but should remain within the Characterization
    feature boundary.
- Documentation:
  - If the implementation needs a new product-level rule for task/result conflict precedence, report
    it so Planning & Reviewing can decide whether to promote it to
    `docs/reference/app/frontend/research-workflow/characterization.md`.

### 9) Cleanup / Retirement
- Cleanup owner: Planning & Reviewing Agent
- Plan artifacts to delete on merge:
  - `Plans/characterization_workbench_state_refactor/Plan.md`
  - `Plans/characterization_workbench_state_refactor/FrontendAgentPrompt.md`
- Decisions to promote to `docs/reference/**` before retirement:
  - Only if Frontend Agent needs to formalize new product semantics beyond this implementation plan.
