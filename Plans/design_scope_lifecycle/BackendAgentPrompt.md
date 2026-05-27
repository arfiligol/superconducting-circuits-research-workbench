# Backend Agent Prompt: Design Scope Lifecycle Backend Authority

## 0) Task Information

- Agent: Backend Agent
- Lane: Backend
- Task ID / Topic: Design Scope lifecycle backend authority
- Prompt Level: `L3 Milestone`
- Branch: `codex/backend-design-scope-lifecycle`
- Worktree: `/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/backend-design-scope-lifecycle`
- Base: `develop` after docs commit `79c739bd6a29f1b7520cc2334944c4e47d6911bc` is merged

Before editing, verify:

```bash
git merge-base --is-ancestor 79c739bd6a29f1b7520cc2334944c4e47d6911bc develop
```

If this exits non-zero, stop and report that `develop` is stale. Do not make code changes.

## 1) Current Problem

HFSS layout imports and circuit simulation publication can currently create separate dataset-local design scopes for the same physical design. The user needs a backend-owned `DesignScope` lifecycle so data from different sources can intentionally land in the same scope and later be merged safely.

The durable SoT now says:

- `DesignScope` is the canonical backend/domain resource.
- Existing-target flows use explicit `dataset_id + design_id`.
- Free-text names are create-new defaults only.
- Merge is backend-owned re-parenting; frontend must not simulate it.
- Merge source becomes `archived` with `redirect_design_id` pointing to target.
- Phase 1 may leave TraceStore physical paths untouched because `store_ref` is opaque.

## 2) Read First

- `docs/reference/data-formats/dataset-record.md`
- `docs/reference/app/backend/datasets-results.md`
- `docs/reference/data-formats/query-indexing-strategy.md`
- `docs/reference/data-formats/analysis-result.md`
- `docs/reference/app/backend/characterization-results.md`
- `docs/reference/guardrails/code-quality/data-handling.md`
- `docs/reference/guardrails/project-basics/backend-architecture.md`
- `docs/reference/guardrails/execution-verification/testing.md`
- `Plans/design_scope_lifecycle/DesignScopeLifecyclePlan.md`

## 3) Allowed Area

- `backend/src/app/domain/**`
- `backend/src/app/services/**`
- `backend/src/app/api/routers/datasets.py`
- `backend/src/app/api/schemas/**`
- `backend/src/app/infrastructure/rewrite_catalog_repository.py`
- `backend/src/app/infrastructure/durable_catalog_repository.py`
- `backend/src/app/infrastructure/persistence/research_data_publication_repository.py`
- Backend migration / persistence model files if required by the accepted implementation.
- Backend tests.
- OpenAPI artifacts only if endpoint contracts change and repo tooling requires regeneration.

## 4) Do Not Touch

- `frontend/**`
- `docs/**`
- `data/raw/**`
- Rejected Gemini worktree `.worktrees/hfss-layout-simulation-ingestion-characterization`
- Physical TraceStore/Zarr path layout unless there is no alternative. Phase 1 should re-parent metadata and keep `store_ref` opaque.

## 5) Required Outcome

Implement DesignScope lifecycle authority in the backend:

- Extend design browse rows with lifecycle truth required by docs: `lifecycle_state`, `redirect_design_id`, row-level `allowed_actions`, and `mutation_policy_summary`.
- Normal list/target selectors should default to active design scopes. Archived/deleted scopes should not become normal ingest, simulation publication, or characterization targets.
- Add backend operations for create, rename, archive/delete soft state, and merge.
- Keep create and rename uniqueness scoped to active design names within one dataset.
- Preserve `design_id` stability on rename.
- Return docs-aligned error codes where applicable: `design_scope_name_conflict`, `target_design_scope_required`, `target_design_scope_invalid`, `design_scope_redirected`, `design_scope_merge_denied`, `design_scope_merge_conflict`.
- Add stale design resolution behavior for archived-with-redirect, archived-without-redirect, and deleted/tombstone states before heavy trace/run/result queries.
- Update raw data ingestion target behavior:
  - `design_id` means existing active target and must be validated.
  - no `design_id` plus a create-new name means create a new active scope.
  - do not silently match free-text name to an existing scope.
  - active-name conflict should reject and instruct caller to select the existing design.
- Update simulation result publication target behavior with the same target rules.
- Implement backend-owned merge re-parenting within one dataset:
  - source and target must be different active scopes.
  - re-parent trace metadata, trace batches, trace-batch links, analysis runs, result artifacts, derived parameters, design assets where they exist in current storage.
  - source becomes archived with `redirect_design_id=target_design_id`.
  - target summaries/read models are refreshed or invalidated.
  - trace/result identities remain stable.
  - TraceStore payload refs are not parsed or moved.
- Make rewrite/local and durable repository paths consistent.

## 6) Constraints

- Keep API handlers thin: parse request, call service, serialize response.
- Keep business decisions in service/domain layer, not frontend or router-only logic.
- Do not introduce a global active design context; dataset remains the shell/session boundary.
- Do not implement downstream fitting, physical mode linking, or cross-source overlay extraction here.
- Prefer backward-compatible request parsing if possible, but report any intentional API shape changes clearly.

## 7) Verification

Run at minimum:

```bash
git diff --check
cd backend && uv run ruff check
cd backend && uv run pytest -q tests/test_rewrite_catalog.py tests/test_simulation_result_publication.py tests/test_local_characterization_integration.py tests/test_characterization_results_integration.py
```

Add focused backend tests covering:

- create active scope and active-name conflict.
- rename preserves `design_id`.
- archive/delete removes scope from normal target list and blocks new ingest/publication/characterization target usage.
- existing-target HFSS/raw ingestion validates active `design_id`.
- create-new ingestion does not hidden-match by free-text name.
- simulation publication validates explicit active `design_id`.
- merge source into target re-parents trace list and result/run history and archives source with redirect.
- stale source `design_id` returns redirect/tombstone behavior before trace/result queries.
- rewrite/local and durable paths stay equivalent for the new lifecycle fields.

If endpoint contracts or OpenAPI snapshots change, also run:

```bash
npm run openapi:check
```

If feasible within time, run full backend suite:

```bash
cd backend && uv run pytest -q
```

## 8) Handoff

Use `Delivery Report v1` and include:

- Branch/worktree and commit hash.
- Changed files with reason.
- API / contract touched matrix.
- Exact endpoint/request/response shape used for lifecycle operations.
- Which records merge re-parents in current implementation.
- Verification commands and results.
- Known risks, especially any durable/rewrite parity gaps or storage structures not yet represented.

