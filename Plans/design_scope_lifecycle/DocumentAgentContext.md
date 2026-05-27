# Document Agent Context: Design Scope Lifecycle and Cross-Source Alignment

## Task Information

- Agent: Document Agent
- Lane: Documentation
- Topic: Design Scope lifecycle and cross-source alignment
- Base: current `develop`
- Plan Artifact: `Plans/design_scope_lifecycle/DesignScopeLifecyclePlan.md`

## Goal

Update the project Source of Truth so implementation agents can safely add Design Scope CRUD, merge, and target-scope selection across Data Ingestion, Simulation publication, Raw Data, and Characterization.

The user need is concrete:

- HFSS layout data and circuit simulation data can represent the same physical design.
- They must be able to land in the same dataset-local analytical scope.
- The user must be able to choose that scope, not rely on auto-created names.
- The system must support scope lifecycle actions such as rename and merge.

## Read First

- `Plans/design_scope_lifecycle/DesignScopeLifecyclePlan.md`
- `docs/reference/data-formats/dataset-record.md`
- `docs/reference/data-formats/query-indexing-strategy.md`
- `docs/reference/data-formats/analysis-result.md`
- `docs/reference/guardrails/code-quality/data-handling.md`
- `docs/reference/guardrails/execution-verification/multi-agent-collaboration.md`

## Required Outcome

Update docs so the following are no longer ambiguous:

- Whether `DesignScope` remains the canonical resource name.
- How `DesignScope` is created, renamed, merged, archived, and deleted.
- How Data Ingestion chooses existing scope vs creates new scope.
- How Simulation save/publish chooses existing scope vs creates new scope.
- How Circuit Definition relates to a DesignScope without making Circuit Definition a relational design-scope table.
- How merge re-parents traces, trace batches, analysis runs, derived parameters, result artifacts, and design assets.
- How deep links and stale `design_id` behave after merge/archive.
- What backend owns vs what frontend may only request.
- What is phase-1 implementation vs later lifecycle enhancements.

## Constraints

- Documentation only. Do not edit production code.
- Do not treat `Plans/` as long-term SoT. Promote durable decisions into `docs/reference/**`.
- `data/raw/**` remains read-only.
- Numeric payload authority remains TraceStore/Zarr.
- `store_ref` is backend-owned opaque locator; do not require frontend to parse or rewrite store paths.
- Keep `DatasetRecord` as the active dataset/session boundary. Do not introduce a global active design context.

## Suggested Documentation Direction

Recommended decisions unless contradicted by existing SoT:

- Canonical backend/domain term stays `DesignScope`.
- UI can label the control `Target Design Scope`.
- Data Ingestion and Simulation publication both send explicit `design_id` when targeting an existing scope.
- Free-text design names are create-new defaults only, not hidden authority.
- Merge is backend-owned re-parenting, not frontend delete/recreate.
- Phase 1 merge may leave TraceStore physical paths untouched because `store_ref` is opaque.
- Source design should become archived or redirected after merge; pick one and document it.

## Verification

Run docs checks:

- `uv run python scripts/check_docs_nav_routes.py --check-source`
- `./scripts/prepare_docs_locales.sh`
- `uv run --group dev zensical build -f zensical.toml`
- `./scripts/build_docs_sites.sh`
- `uv run python scripts/check_docs_nav_routes.py --check-built`

## Handoff

Delivery Report must include:

- Commit hash.
- Changed docs.
- Exact lifecycle decisions made.
- Any open decisions that still need the user.
- Whether implementation can begin, or what remains blocked.

