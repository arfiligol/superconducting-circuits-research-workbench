# ND Trace And Characterization Result Model Implementation Plan

This file is an execution plan for the next implementation phase.
It does not replace `docs/reference/**`.
The owner contracts remain in the accepted docs SoT; this file exists to drive planning, prompt-writing, and review order.

## 0) Task Information

- Agent: `Planning Agent`
- Task ID / Topic: `M6-ND-Trace-And-Characterization-Result-Model`
- Status: `Ready for implementation planning 2026-03-30`

## 1) Goal

Implement the newly accepted canonical data/result direction so the platform can move from:

- point-trace-oriented persistence and scalar-style characterization outputs

to:

- canonical ND `TraceRecord`
- summary-first trace/query surfaces
- phase-1 `collection_projection`
- trace-structure-derived Characterization input collections
- axis-aware Characterization results, starting with `admittance_extraction`

The immediate user-facing success condition is:

1. simulation / publication paths can persist sweep-aware ND traces truthfully
2. dataset/design trace browse can query them efficiently without opening dense payloads by default
3. Characterization can derive an input collection from canonical trace structure
4. `admittance_extraction` can persist and serve a mode-by-sweep result model
5. frontend can inspect that result through table / plot presets instead of a scalar-style detail view

## 2) Source Of Truth

Primary owner docs:

- `docs/reference/data-formats/dataset-record.md`
- `docs/reference/app/backend/datasets-results.md`
- `docs/reference/app/backend/characterization-results.md`
- `docs/reference/guardrails/code-quality/data-handling.md`
- `docs/reference/app/frontend/research-workflow/characterization.md`

Planning / execution rules:

- `docs/reference/guardrails/execution-verification/prompt-grading.md`
- `docs/reference/guardrails/execution-verification/branch-and-worktree-flow.md`
- `docs/reference/guardrails/execution-verification/multi-agent-collaboration.md`

## 3) Current Agreed Phase-1 Boundaries

Already frozen in docs:

- canonical authority is ND `TraceRecord`
- `NaN` means invalid / unavailable numeric cell
- analysis is mask-first
- fully masked slices remain present in the canonical grid
- metadata/query paths are summary-first
- `collection_projection` is a derived read model, not a persisted authority resource
- `collection_key` is structural identity only
- phase-1 sweep filtering is limited to axis-name / collection-level / summary-safe filtering
- `mode_index` is ordinal per sweep point, not physical mode tracking
- large-result transport is slice/preset-first, not whole-dense by default

Still intentionally open:

- exact field names
- exact `axis_signature` formula
- exact `collection_key` formula
- chunk size / byte limits
- value-level sweep filtering contract
- whether dependent results are invalidated or recomputed per artifact class

These remaining open items do not block implementation planning.

## 4) Planning Rule For This Workstream

This workstream should default to broad implementation slices.

- Prefer `L3 Milestone` or broad `L2 Slice`
- Use `Allowed Area` + `Do Not Touch`
- Do not prematurely shrink prompts to tiny file lists
- Let review + fixup tighten the outcome after a real pass

Only use narrow `L1 Fixup` prompts after a concrete mismatch is discovered.

## 5) Implementation Milestones

### Milestone A: Core / Backend ND Trace Persistence And Summary Surfaces

- Prompt level:
  - `L3 Milestone`
- Goal:
  - establish the backend/core storage path for canonical ND traces
  - materialize the required summary metadata for query/filter/readiness use
  - keep dense coordinates and dense numeric values in `TraceStore`
- Allowed Area:
  - `core/**`
  - `backend/src/app/infrastructure/**`
  - `backend/src/app/services/**`
  - `backend/tests/**`
  - `tests/core/**`
- Do Not Touch:
  - `frontend/**`
  - `docs/**`
  - unrelated runtime/session/auth areas
- Required outcome:
  - ND `TraceRecord` persistence path exists
  - metadata summary includes rank/shape/axis summary/typing/grouping inputs
  - list/filter/readiness paths can operate without opening dense coordinates by default
  - any legacy point-trace fallback remains projection-only, not authority

### Milestone B: Backend Collection Projection And Characterization Input Collection

- Prompt level:
  - `L3 Milestone`
- Goal:
  - derive phase-1 `collection_projection` from canonical trace structure
  - derive `input_collection_payload` for Characterization from selected traces
- Allowed Area:
  - `backend/src/app/domain/**`
  - `backend/src/app/services/**`
  - `backend/src/app/api/**`
  - `backend/src/app/infrastructure/**`
  - `backend/tests/**`
- Do Not Touch:
  - `frontend/**`
  - docs beyond minimal sync explicitly requested later
- Required outcome:
  - deterministic structural `collection_key`
  - Characterization selection can resolve a collection from selected traces
  - phase-1 filtering remains summary-safe
  - no analysis-specific readiness leaks into collection identity

### Milestone C: Backend `admittance_extraction` Result Contract Cutover

- Prompt level:
  - `L3 Milestone`
- Goal:
  - replace the current scalar-style persisted result model with a phase-1 axis-aware result contract
- Allowed Area:
  - `backend/src/app/domain/**`
  - `backend/src/app/services/**`
  - `backend/src/app/infrastructure/**`
  - `backend/src/app/api/**`
  - `backend/tests/**`
  - `core/**` if shared artifact/result contracts need it
- Do Not Touch:
  - unrelated frontend surfaces
  - unrelated characterization methods unless required for shared contract alignment
- Required outcome:
  - `admittance_extraction` persists result axes and artifact manifest in phase-1 form
  - result payload supports:
    - rows = `mode_index`
    - columns or x-axis = sweep axis such as `L_jun`
    - metric = `frequency_ghz`
  - result payload queries are preset/slice-aware
  - scalar-only frontend assumptions are no longer required for this method

### Milestone D: Frontend Characterization Trace Filtering And Result Explorer Adoption

- Prompt level:
  - `L3 Milestone`
- Goal:
  - adopt the new backend collection/result surfaces in Characterization
- Allowed Area:
  - `frontend/src/features/characterization/**`
  - `frontend/src/lib/api/**`
  - `frontend/tests/**`
- Do Not Touch:
  - backend contracts
  - unrelated Simulation page UI except for shared explorer primitives if needed
- Required outcome:
  - Stage 1 can consume phase-1 collection/filter summaries
  - Result Detail can render method-aware axis/preset content for `admittance_extraction`
  - table/plot explorer behavior aligns with the new result contract
  - UI remains truthful about phase-1 limits:
    - no physical mode tracking claim
    - no value-level sweep filtering claim

### Milestone E: End-To-End Verification And Fixup Loop

- Prompt level:
  - `L2 Slice` or `L1 Fixup`, depending on what remains
- Goal:
  - verify the real integrated path and close the first round of mismatches
- Allowed Area:
  - whatever area the live mismatch points to
- Do Not Touch:
  - unrelated cleanup
- Required outcome:
  - live simulation/publication -> dataset/design trace browse -> Characterization -> persisted result inspection works on the new contract
  - review/fixup loop closes real mismatches, not only test fixtures

## 6) Non-Goals For Phase-1

- no physical `mode_track_id`
- no coordinate-value / range filtering on trace list paths
- no full generalized collection resource (`TraceCollectionRecord`)
- no whole-dense tensor transport as the default result contract
- no redesign of unrelated characterization methods unless required by shared result infrastructure
- no docs rewrite during implementation slices except explicit doc-sync follow-ups

## 7) Verification Matrix

### Backend / Core

- `cd backend && uv run ruff check`
- `cd backend && uv run pytest -q`
- `uv run pytest -q tests/core/**` where relevant

### Frontend

- `npm install --prefix frontend`
- `npm run typecheck --prefix frontend`
- `npm run test --prefix frontend`

### Runtime / Integration

- publish or ingest a representative sweep-aware trace case
- browse it from dataset/design trace surfaces
- verify summary-first filtering behavior
- run `admittance_extraction`
- reopen persisted result after refresh
- verify table / plot presets from the real backend payload

### Docs Sync After Contracted Changes

Only if implementation reveals contract drift:

- `uv run python scripts/check_docs_nav_routes.py --check-source`
- `./scripts/prepare_docs_locales.sh`
- `uv run --group dev zensical build -f zensical.toml`
- `./scripts/build_docs_sites.sh`
- `uv run python scripts/check_docs_nav_routes.py --check-built`

## 8) Review Focus

Each delivery report in this workstream should be reviewed against:

- real diff scope
- real persisted/runtime behavior
- SoT alignment with the accepted ND-trace/result-contract docs
- whether the worker solved the real integrated case, not only synthetic tests

Special attention:

- no hidden fallback back to point-trace authority
- no dense-payload reads on summary/list paths by default
- no collection identity drift from analysis-specific readiness
- no scalar-only result shortcut left behind in `admittance_extraction`

## 9) Risks

- ND trace persistence may expose legacy assumptions in trace preview/edit surfaces
- collection derivation may drift unless all services use the same helper logic
- `admittance_extraction` may require artifact/result refactoring beyond one repository or service boundary
- frontend may need a small shared explorer primitive rather than a one-off local renderer
- live payload size may still force one round of backend/fronted fixup even if the contract is correct

## 10) Recommended Execution Order

1. Milestone A
2. Milestone B
3. Milestone C
4. Review + fixup if needed
5. Milestone D
6. Review + fixup if needed
7. Milestone E

Do not start Frontend adoption before the backend result contract for `admittance_extraction` is stable enough to consume.

## 11) Exit Condition

This plan can be retired once:

- canonical ND trace persistence is real, not just documented
- metadata summary powers query/filter/readiness paths without dense reads by default
- phase-1 `collection_projection` and Characterization input collection are implemented and stable
- `admittance_extraction` serves a persisted axis-aware result contract
- Characterization frontend can inspect that result through phase-1 table/plot presets
- remaining gaps are small enough to be handled as narrow fixups instead of another architecture phase
