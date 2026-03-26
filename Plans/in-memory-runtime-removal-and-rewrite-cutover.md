# Plan Artifact v1

## 0) Task Information

- Agent: `Planning Agent`
- Task ID / Topic: `M5-In-Memory-Runtime-Removal-And-Rewrite-Cutover`
- Status: `Active follow-up cleanup after major cutover landed on main 2026-03-26`

## 1) Goal

- 目標:
  把 backend 目前仍以 in-memory repository / seeded runtime data 承擔 authority 的部分移除，改成正式的 metadata DB + TraceStore + explicit backend seed path。
- 使用者成功條件:
  - `Simulation`、`Raw Data`、`Characterization`、`Circuit Definitions` 這些正式資料 surface 不再依賴 in-memory store 當 authority
  - backend startup 不再用 constructor seed 產生 demo/catalog/task data 作為正式執行資料來源
  - 若需要 seed，必須透過 backend seed path 寫入 DB / TraceStore
  - `Rewrite*` / `InMemory*Repository` 這類 migration residue 不再是 active runtime canonical path

## 2) Source of Truth

- Primary docs:
  - `docs/reference/guardrails/project-basics/backend-architecture.md`
  - `docs/reference/guardrails/project-basics/tech-stack.md`
  - `docs/reference/guardrails/code-quality/data-handling.md`
  - `docs/reference/app/backend/datasets-results.md`
  - `docs/reference/app/backend/circuit-definitions.md`
  - `docs/reference/app/shared/runtime-modes.md`
  - `docs/reference/app/shared/observability-model.md`
- Current authority owner:
  backend persistence / TraceStore direction is defined in `docs/reference/**`; `Plans/**` only tracks execution.

## 3) Current Implementation State

- Landed on `main`:
  - active runtime scientific/data authority no longer depends on in-memory catalog ownership
  - durable dataset / design / trace / characterization / circuit-definition cutover landed
  - durable published-trace delete and deterministic seed reset landed
  - durable session / auth / app-state cutover landed
  - backend service-slimming slices reduced the largest task/dataset/explorer hotspots
- Remaining gaps:
  - non-active `Rewrite*` / `InMemory*` residue still exists and should be cleaned up deliberately
  - naming cleanup is still incomplete even though active ownership changed
  - restart-stable browser/runtime verification still matters for confidence beyond backend tests
  - request-debug/logging hardening remains tracked separately in `Plans/backend-request-debug-logging-followup.md`

## 4) Implementation Slices

### Backend Persistence Cutover `[Landed on main]`

- Allowed Area:
  - `backend/src/app/infrastructure/**`
  - `backend/src/app/services/**`
  - `backend/src/app/api/**`
  - `backend/tests/**`
  - seed/migration scripts if needed
- Do Not Touch:
  - `frontend/**`
  - `desktop/**`
  - `docs/**` except doc sync slices explicitly opened later
- Goal:
  replace active in-memory data authority with durable repository boundaries for:
  - dataset catalog/profile lifecycle
  - design browse/create
  - raw trace ingest/list/detail/edit/delete
  - characterization registry/history/results/tagging
  - circuit definition list/detail/mutation read path

### Session / Auth / Workspace State Cutover `[Landed on main]`

- Allowed Area:
  - `backend/src/app/infrastructure/**`
  - `backend/src/app/services/session_service.py`
  - `backend/src/app/services/workspace_collaboration_service.py`
  - related backend tests
- Do Not Touch:
  - scientific execution logic
  - frontend shell/auth UI in the first slice
- Goal:
  decide and implement which backend session/app-context/workspace state must become durable instead of process-local memory.

### Naming / Topology Cleanup `[Remaining]`

- Allowed Area:
  - backend runtime / infrastructure naming
  - tests and docs that reference the renamed owners
- Do Not Touch:
  - unrelated product copy
- Goal:
  remove active runtime residue naming such as:
  - `Rewrite*`
  - `InMemory*Repository`
  where those names no longer represent intended canonical ownership.

### Seed Strategy Cutover `[Landed on main]`

- Allowed Area:
  - backend seed scripts
  - migrations/bootstrap paths
  - tests/docs for seed behavior
- Do Not Touch:
  - frontend-only fixture helpers
- Goal:
  replace constructor/bootstrap in-memory seeds with explicit backend seed flows that write:
  - metadata DB
  - TraceStore
  - audit/task stores where relevant

## 5) Test Backlog

- Integration:
  - dataset create/update/archive survives backend restart
  - raw data ingest survives backend restart
  - saved simulation traces appear from durable storage only
  - characterization results/tagging survive backend restart
  - circuit definition create/update/delete survives backend restart without in-memory cache bootstrap
  - session/auth behavior remains coherent across process restart if moved to durable state
- E2E:
  - browser-driven Raw Data CRUD against durable traces only
  - Local Mode simulation -> save traces -> Raw Data -> characterization after backend restart
  - no seeded in-memory demo rows reappearing after restart unless explicit seed command was run

## 6) Verification Matrix

- Static audit:
  - `rg -n "InMemory|_seed_|build_seed_tasks|seed_tasks|Rewrite" backend/src`
- Backend:
  - `cd backend && uv run ruff check`
  - `cd backend && uv run pytest -q`
- Docs sync after implementation:
  - `uv run python scripts/check_docs_nav_routes.py --check-source`
  - `./scripts/prepare_docs_locales.sh`
  - `uv run --group dev zensical build -f zensical.toml`
- Runtime verification:
  - restart backend and prove persisted data remains correct
  - explicit seed command creates data only when invoked

## 7) Risks / Open Decisions

- Session/auth/workspace state may need a dedicated durable repository rather than piggybacking on dataset/task persistence.
- Characterization registry availability may currently depend on seeded demo rows plus derived task projections; this needs a clean authority split before removal.
- Circuit Definitions already persist writes, but active reads still go through the mixed catalog owner; refactor order matters.
- `Rewrite` naming cleanup should not be done as pure rename churn before persistence boundaries are stabilized.
- Seed strategy likely needs both:
  - explicit dev seed command
  - explicit test fixture seeding path
  instead of one constructor path trying to satisfy runtime, demo, and tests at once.

## 8) Recommended Execution Order

1. Remove remaining non-active `Rewrite*` / `InMemory*` residue where ownership already moved
2. Re-check docs / code naming parity after the cleanup
3. Run live restart-stable browser/runtime verification on the durable path
4. Retire this plan once only archival residue remains

## 9) Exit Condition

This plan can be retired once:

- active backend runtime no longer wires scientific/data surfaces to `InMemory*Repository`
- startup no longer materializes demo/scientific authority data in constructor memory
- all required seed data enters through explicit backend seed flows into DB / TraceStore
- `Simulation`, `Raw Data`, `Characterization`, and `Circuit Definitions` are restart-stable from durable storage
- remaining `Rewrite` naming, if any, is either removed or explicitly documented as non-runtime archival residue
