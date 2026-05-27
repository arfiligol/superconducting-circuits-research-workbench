# Plan Artifact v2: Design Scope Lifecycle and Cross-Source Alignment

Date: 2026-04-30
Status: Documentation accepted; implementation prompts prepared; implementation starts only after docs commit is merged into `develop`
Lifecycle State: active
Owner: Planning & Reviewing Agent in current Codex thread
Supersedes: none
Retirement Criteria: retire after accepted docs, backend, frontend, and test slices are integrated into `develop`; promote durable decisions to `docs/reference/**` before retirement.

## 0) Current Review State

Documentation slice accepted:

- Commit: `79c739bd6a29f1b7520cc2334944c4e47d6911bc`
- Branch/worktree: `codex/docs-design-scope-lifecycle` / `.worktrees/docs-design-scope-lifecycle`
- Subject: `docs: define design scope lifecycle contract`
- Verified during Planning & Review:
  - `git diff --check 79c739bd6a29f1b7520cc2334944c4e47d6911bc^ 79c739bd6a29f1b7520cc2334944c4e47d6911bc`
  - `uv run python scripts/check_docs_nav_routes.py --check-source`

Implementation prerequisite:

```bash
git merge-base --is-ancestor 79c739bd6a29f1b7520cc2334944c4e47d6911bc develop
```

Implementation agents must stop before code changes if this command exits non-zero.

## 1) Goal

Make dataset-local `DesignScope` a first-class user-managed analytical scope so layout simulation, circuit simulation, measurement, and downstream characterization assets can intentionally land in the same scope.

User success conditions:

- Data Ingestion can import HFSS / measurement traces into an existing design scope or create a new one.
- Simulation trace/result save can target an existing design scope or create a new one, instead of accidentally creating a parallel scope.
- Raw Data / Dataset surfaces expose safe Design Scope CRUD: create, rename, merge, and archive/delete where allowed.
- Characterization uses the selected `dataset_id + design_id` as stable authority; tasks/results from other scopes cannot pull the page into a different scope.
- Cross-source comparison becomes possible inside one scope, for example PF6FQ layout `Y11 Im` and circuit-simulation `Y11 Im` traces under the same PF6FQ Q0 scope.

## 2) Source of Truth

Primary docs already relevant:

- `docs/reference/data-formats/dataset-record.md`
- `docs/reference/data-formats/query-indexing-strategy.md`
- `docs/reference/data-formats/analysis-result.md`
- `docs/reference/guardrails/code-quality/data-handling.md`
- `docs/reference/guardrails/execution-verification/multi-agent-collaboration.md`

Accepted SoT decisions from `79c739b`:

- Canonical backend/domain term remains `DesignScope`; UI may label the selector `Target Design Scope`.
- Existing-target flows must send explicit `dataset_id + design_id`.
- Free-text names are create-new defaults only; no hidden name-to-existing-scope authority.
- Merge is backend-owned re-parenting, not frontend delete/recreate.
- Merge source becomes `archived` with `redirect_design_id` pointing to target.
- Merge re-parents traces, trace batches, trace-batch links, analysis runs, result artifacts, derived parameters, design assets, readiness summaries, and design-scoped read models.
- Phase 1 may leave TraceStore physical paths untouched because `store_ref` is backend-owned and opaque.
- Circuit Definition remains document-first and may associate to a DesignScope via `DesignAssetRecord` or equivalent backend-owned association.
- Dataset remains the active dataset/session boundary; no global active design context is introduced.

## 3) Current Implementation State

Existing useful paths:

- `backend/src/app/services/dataset_service.py`: dataset service already exposes `create_design(...)`.
- `backend/src/app/api/routers/datasets.py`: datasets router owns design-scoped routes.
- `backend/src/app/infrastructure/rewrite_catalog_repository.py`: raw ingestion picks `draft.design_id` or derives one from `draft.design_name`.
- `backend/src/app/infrastructure/persistence/research_data_publication_repository.py`: simulation publication similarly picks `draft.design_id` or derives from `draft.design_name`.
- `frontend/src/features/data-browser/components/data-ingestion-workspace.tsx`: upload-first ingestion currently presents `Design Name`, not a target design scope selector.
- `frontend/src/features/data-browser/lib/upload-first-ingestion.ts`: `buildUploadFirstIngestionDraft(...)` always sends `design_id: null`.
- `frontend/src/features/simulation/components/current-trace-save-control.tsx`: save traces flow already lists existing design scopes and can create one.
- `frontend/src/features/data-browser/components/raw-data-design-scopes-panel.tsx`: Raw Data can browse design scopes but cannot manage lifecycle.
- `frontend/src/features/characterization/hooks/use-characterization-workflow-data.ts`: local fix in progress prevents out-of-scope task/result selection from pulling the page away from the requested design.

Observed real issue:

- Active dataset has separate scopes:
  - `design_floatingqubitwithxy`: circuit simulation traces.
  - `design_pf6fq-q0`: layout simulation traces.
- This prevents same-scope characterization and comparison even when both data sources correspond to the same physical device/design.

## 4) Terminology Decision Needed

Current canonical term is `DesignScope`.

Recommendation:

- Keep backend/domain term as `DesignScope`.
- UI labels may say `Design Scope` or `Target Design Scope`.
- Avoid introducing a separate canonical `DataScope` unless Documentation Agent explicitly decides to rename the resource. `Data Scope` is ambiguous with `Dataset`.

## 5) Implementation Prompt Files

Use these lane prompts after `79c739b` is merged into `develop`:

- `Plans/design_scope_lifecycle/BackendAgentPrompt.md`
- `Plans/design_scope_lifecycle/FrontendAgentPrompt.md`
- `Plans/design_scope_lifecycle/TestAgentPrompt.md`

## 6) Implementation Slices

### Slice A: Documentation Agent

Status: accepted in `79c739bd6a29f1b7520cc2334944c4e47d6911bc`.

Allowed Area:

- `docs/reference/data-formats/dataset-record.md`
- `docs/reference/data-formats/query-indexing-strategy.md`
- `docs/reference/data-formats/analysis-result.md`
- relevant frontend workflow docs if present under `docs/reference/app/frontend/**`

Goal:

- Freeze the Design Scope lifecycle and cross-source alignment contract.
- Define CRUD / merge / archive behavior before backend or frontend implementation.

Do Not Touch:

- production code.
- test fixtures.
- raw data.

### Slice B: Backend Agent

Prompt Level: `L3 Milestone`.

Start only after Slice A is accepted and merged to `develop`.

Allowed Area:

- dataset domain/service/repository/router layers;
- persistence models / migrations if the accepted docs require schema changes;
- generated OpenAPI artifacts if endpoint contracts change;
- backend tests.

Goal:

- Implement Design Scope lifecycle backend authority.
- Add API support for rename, merge, archive/delete, and existing-scope ingestion target.
- Ensure simulation publication and raw ingestion respect explicit `design_id`.
- Preserve metadata/read-model summaries and do not move dense numeric payload unless required by accepted SoT.

Likely endpoints:

- `POST /datasets/{dataset_id}/designs` already exists or can be reused.
- `PATCH /datasets/{dataset_id}/designs/{design_id}` for rename / lifecycle metadata.
- `POST /datasets/{dataset_id}/designs/{source_design_id}/merge` for merge into target.
- `DELETE /datasets/{dataset_id}/designs/{design_id}` or lifecycle patch for archive/delete.

Non-goals:

- Do not implement physical mode linking.
- Do not implement downstream fitting.
- Do not change raw data layout.

### Slice C: Frontend Agent

Prompt Level: `L3 Milestone`.

Start only after Slice A is accepted and merged to `develop`.
Frontend can proceed in parallel with Backend if it keeps all API calls centralized and reports any assumed endpoint shape explicitly.

Allowed Area:

- Data Ingestion UI;
- Raw Data Design Scopes panel;
- Simulation save/publish dialogs;
- Characterization URL/state guard if more UI polish is needed;
- frontend tests.

Goal:

- Replace Data Ingestion free-text-only design entry with `Target Design Scope`: choose existing or create new.
- Keep filename-derived suggestion as a create-new default, not as hidden authority.
- Add Design Scope lifecycle UI in Raw Data / Dataset:
  - create;
  - rename;
  - merge into another scope;
  - archive/delete where allowed.
- Simulation save/publish should use the same target design scope interaction model as Data Ingestion.

Non-goals:

- No new global session-level design context.
- No frontend-only merge logic; merge must call backend authority.

### Slice D: Test Agent

Prompt Level: `L2 Slice`.

Start after accepted backend/frontend integration branch exists.

Goal:

- Verify cross-source same-scope workflow end to end.

Required scenarios:

- Ingest HFSS PF6FQ trace into an existing target design scope.
- Save/publish circuit simulation trace into the same target design scope.
- Verify Raw Data scope source coverage shows both `layout_simulation` and `circuit_simulation`.
- Verify Characterization registry sees both traces within one `dataset_id + design_id`.
- Verify merge source scope into target scope re-parents trace list and result history according to accepted contract.
- Verify stale links to archived/source scope behave according to accepted contract.

## 7) Verification Matrix

Documentation:

- `uv run python scripts/check_docs_nav_routes.py --check-source`
- `./scripts/prepare_docs_locales.sh`
- `uv run --group dev zensical build -f zensical.toml`
- `./scripts/build_docs_sites.sh`
- `uv run python scripts/check_docs_nav_routes.py --check-built`

Backend:

- `cd backend && uv run ruff check`
- `cd backend && uv run pytest -q <new design scope tests>`
- `cd backend && uv run pytest -q tests/test_rewrite_catalog.py tests/test_local_characterization_integration.py tests/test_hfss_ingestion_integrated.py`
- `npm run openapi:check` if API artifacts change.

Frontend:

- `npm run typecheck --prefix frontend`
- `npm run test --prefix frontend -- data-browser.test.ts characterization-workflow.test.ts simulation-workflow.test.ts`
- Browser smoke for:
  - Data Ingestion target scope selection.
  - Raw Data scope rename/merge.
  - Characterization same-scope browse.

Integration / E2E:

- default test suite must not require untracked PF6FQ raw data.
- opt-in real-data E2E may use:
  - `RUN_HFSS_REAL_DATA_E2E=1`
  - `PF6FQ_RAW_DATA_ROOT=/Users/arfiligol/Github/superconducting-circuits-tutorial/data/raw/layout_simulation/PF6FQ`

## 8) Risks / Open Decisions

- Merge semantics can corrupt lineage if implemented as simple frontend delete/recreate. Backend must own re-parenting.
- TraceStore paths may include old design ids. This is acceptable only if `store_ref` is treated as opaque locator and metadata DB remains query authority.
- Circuit Definition to DesignScope relationship is under-specified. Documentation Agent must decide whether phase 1 uses `DesignAssetRecord`, design metadata links, or a lighter association.
- Archive/delete behavior must consider existing analysis runs and deep links.
- If DesignScope is renamed to DataScope in UI, docs must define whether this is label-only or canonical resource rename.

## 9) Cleanup / Retirement

Cleanup owner: Planning & Reviewing Agent in this thread.

Plan artifacts to retire:

- `Plans/design_scope_lifecycle/DesignScopeLifecyclePlan.md`
- lane-specific prompts created under `Plans/design_scope_lifecycle/`

Retire after:

- accepted SoT docs exist;
- backend/frontend/test slices are integrated;
- final verification passes;
- durable decisions have moved into `docs/reference/**`.
