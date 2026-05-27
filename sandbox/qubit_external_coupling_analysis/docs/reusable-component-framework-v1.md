# Reusable Component Framework v1

Framework v1 defines a sandbox-only semantic layer for superconducting-circuit design. Components declare reusable local structure, relations declare cross-component design intent, and finalization is the only stage that resolves the semantic graph into JosephsonCircuits rows.

This is not a `core/` migration. The framework remains inside `sandbox/qubit_external_coupling_analysis/` until the design is proven by user-facing examples and implementation-facing contracts.

## Documentation Map

| Page | Audience | Source-of-truth role |
| --- | --- | --- |
| [Learn](reusable-component-framework-v1/learn.md) | Researchers and users assembling circuits | User-friendly SoT for how the framework should feel to use |
| [Authoring](reusable-component-framework-v1/authoring.md) | Developers extending helpers/components | Implementation-friendly SoT for responsibility boundaries and review rules |

Read **Learn** first if the task is "I want to build a circuit." Read **Authoring** first if the task is "I want to add a reusable component or helper."

## Why Split Learn and Authoring

The framework has two different truth surfaces:

- **Learn is user-friendly SoT.** If a common circuit is hard to explain in Learn, the design is probably not user friendly enough.
- **Authoring is implementation-friendly SoT.** If a helper cannot be implemented from Authoring without guessing responsibility boundaries, the contract is not clear enough.

The two pages should stay consistent but not identical. Learn hides internal mechanics until they affect user choices. Authoring exposes the mechanics because helper implementation depends on them.

## Design Health Review

The current prototype is useful, but it is not yet a complete framework. The largest current gap is user friendliness: early drafts made users learn terms such as `LineTap`, `LineSpan`, primitive rows, and lowering behavior before they could assemble a normal circuit.

Framework v1 treats that as a design smell. Learn must lead with task-first recipes and friendly facade helpers. Authoring then maps those facade helpers back to explicit implementation contracts.

| Area | Current risk | v1 response |
| --- | --- | --- |
| User API | Users still need to understand too much about internal nodes, line splitting, and draft lowering | Learn leads with copyable workflows and hides internal terms until the concept reference |
| Facade naming | Julia pseudo-method examples such as `q1.pin(:pad)` can look friendlier than they are implementable | Learn uses function-style facade helpers such as `pin(q1, :pad)`, `tap(bus, 0.25)`, and `finalize_circuit(draft)` |
| Component interface | Existing helpers behave like components but do not share a formal metadata contract | Authoring defines component metadata, pins, anchors, owned lines, and lowering rules |
| Coupling helpers | Coupling can look like a side effect instead of a design object | Authoring makes composition relations first-class |
| Distributed lines | Line taps/windows can tempt helpers to mutate pre-expanded ladder nodes | Authoring requires declarative segmentation requests before primitive lowering |
| Traceability | Flat netlists lose semantic origin unless mapping is planned | Authoring defines provenance as required diagnostic metadata |
| Sweep design | Component parameters and relation parameters can be mixed together | Both pages define semantic multi-parameter sweeps with explicit component/relation ownership |
| Agent usage | A future agent could assemble circuits by private node guessing | Learn and Authoring now include Skill-ready rules for building components and assembling circuits |

## Framework Direction

v1 uses a breaking-change implementation path inside the sandbox. This is still heavy development, not a public service contract.

1. Preserve low-level physical lowering utilities such as `RLGCSpec`, `CoupledWindowSpec`, distributed segment emission, and MTL row emission.
2. Replace old draft authoring helpers with the Framework v1 semantic API.
3. Require concrete component subtypes, endpoint refs, relations, segmentation requests, finalization artifacts, provenance, and semantic sweeps to exist as explicit Julia concepts.
4. Add user-facing helper vocabulary only when Learn can explain it without exposing private node names, line-realization internals, or solver-facing rows.
5. Require each friendly Learn helper to map to exactly one Authoring contract.
6. Do not keep compatibility wrappers for old sandbox helpers during this fast-iteration phase.

## Non-Goals

Framework v1 does not:

- move sandbox logic into `core/`
- migrate backend/frontend/UI schemas
- replace JosephsonCircuits.jl
- generate physical layout
- extract parameters from GDS, HFSS, Q3D, or FEM
- perform symbolic quantization
- support every possible distributed-circuit conflict

## Acceptance Criteria

The documentation split is successful when:

- a user can follow Learn to assemble a typical circuit without reading `circuit_draft.jl`
- a developer can follow Authoring to add a helper without inventing responsibility boundaries
- any future helper can be reviewed against Authoring invariants
- any awkward Learn recipe becomes an actionable API design smell
