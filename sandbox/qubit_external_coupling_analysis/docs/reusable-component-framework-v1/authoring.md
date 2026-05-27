# Authoring: Reusable Component Framework v1

Authoring is the implementation-facing source of truth. It defines responsibility boundaries, helper contracts, and review rules for extending the sandbox reusable-component framework.

If a helper cannot be implemented from this page without guessing who owns validation, segmentation, lowering, or provenance, the Authoring contract is incomplete.

## Core Responsibility Split

Framework v1 separates declaration, composition, resolution, and primitive emission.

| Layer | Owns | Must not do |
| --- | --- | --- |
| Primitive Layer | Solver-facing rows such as `L`, `C`, `R`, `P`, `K` | Act as semantic source of truth |
| Component Layer | Reusable local structure and intrinsic parameters | Own cross-component interactions |
| Composition Layer | First-class relations and interaction parameters | Emit primitive rows before finalization |
| Finalization Layer | Validation, anchor resolution, segmentation, lowering, node naming, provenance | Silently change design intent |

Data flow:

```text
Component declarations
        |
        v
CircuitDraft semantic graph
        |
        v
Composition relations
        |
        v
Finalization artifact
        |
        v
JosephsonCircuits netlist + provenance + node map + segmentation plan
```

## Responsibility Boundaries

| Object / Layer | Owns | May request | Must not do |
| --- | --- | --- | --- |
| `Component` | intrinsic parameters, public pins, public anchors, owned abstract lines, ground convention, uncoupled lowering rule | local validation | inspect other components, emit cross-couplings, decide global primitive nodes |
| `Pin` | discrete endpoint identity | resolution during finalization | encode distributed spans |
| `LineTap` | semantic position on a distributed line | boundary insertion when used by a relation | imply a physical split by itself |
| `LineSpan` | semantic interval on a distributed line | section replacement | directly emit MTL rows |
| `PortAnchor` | simulation or measurement intent | port row emission during finalization | act as a generic electrical endpoint |
| `GroundAnchor` | reference convention | ground consistency checks | force global ground merges by itself |
| `CompositionRelation` | relation id, kind, endpoints, interaction parameters, modification mode, required segmentation | additive or replacement effects | mutate component internals, assume private node names, emit primitive rows |
| `SegmentationRequest` | requested split or span boundary | merged segmentation plan | decide final chunks alone |
| `CircuitDraft` | registered components, relations, unresolved references, global namespace, finalization configuration | finalization | solver-specific physics interpretation |
| `Finalization` | graph validation, endpoint compatibility, anchor resolution, segmentation plan, conflict detection, lowering order, node naming, primitive emission, provenance | errors or warnings on conflicts | silently change component or relation parameters |
| `PrimitiveRow` | solver-facing row | carry provenance | become the source of truth for semantic authoring |

## Design Invariants

Reject an implementation that violates these rules.

- Component internal nodes are private by default.
- Anchors are semantic references, not primitive nodes.
- A `LineTap` does not imply a physical split unless a relation requires it.
- Only `Pin` and resolved `LineTap` endpoints are discrete connectable endpoints.
- `connect_pins!` means ideal node equivalence between compatible discrete pins only.
- `LineSpanRef` is never valid for `connect_pins!`; use `coupled_window!` or another span relation.
- Composition helpers create relations and optional segmentation requests; they do not emit primitive rows.
- Segmentation requests are declarative and order-independent.
- Line splitting happens before primitive lowering.
- Relation modification mode must be explicit: `additive`, `segmentation-only`, `replacement`, or `annotation-only`.
- Components declare local capabilities; helpers and finalization validate cross-component compatibility.
- Primitive rows may carry provenance, but must not encode high-level behavior as authority.
- Component `id` and relation `id` must remain stable across finalization.
- Overlapping replacement spans on the same line are invalid in v1 unless explicitly documented.
- Finalization should be non-destructive by default.

## Learn Facade Mapping

Learn may use friendlier names than the internal implementation, but every Learn facade helper must map to exactly one documented Authoring contract. A facade name is acceptable only when this table or a future replacement table defines its implementation meaning.

| Learn facade | Authoring construct | Contract requirement |
| --- | --- | --- |
| `CircuitDraft(name)` | `CircuitDraft` semantic graph container | Creates an empty draft; must not lower components |
| `lc_resonator!` | `LCResonatorComponent` | Registers an LC resonator component with pins, intrinsic parameters, and uncoupled lowering rule |
| `lc_qubit!` | `LCQubitComponent` | Registers an LC-like qubit component with public pins and ground convention |
| `tunable_coupler!` | `TunableCouplerComponent` | Registers a tunable LC coupler component with explicit component-owned tuning parameters |
| `cpw_line!` | `CPWLineComponent` | Registers a CPW-like line component without expanding private ladder nodes immediately |
| `quarter_wave_resonator!` | `QuarterWaveResonatorComponent` | Registers a QWR component with boundary conditions and public taps/spans |
| `pin(component, :name)` | `PinRef` | Resolves to a public discrete endpoint only |
| `tap(component, x)` | `LineTapRef` | Creates a semantic line-position reference; segmentation happens only when a relation uses it |
| `tap_m(component, x_m)` | `LineTapRef(mode=:meter)` | Creates an absolute-position line tap in meters |
| `section(component, a, b)` | `LineSpanRef` | Creates a semantic line-interval reference for span relations |
| `section_m(component, a_m, b_m)` | `LineSpanRef(mode=:meter)` | Creates an absolute interval in meters |
| `ground()` | ground convenience reference | Must resolve through an explicit ground/reference convention, not a private node name |
| `measurement_port(...)` | `PortAnchor` | Adds simulation intent; must not become a generic coupling endpoint |
| `ground_reference(...)` | `GroundAnchor` | Adds reference convention metadata; must not force a global ground merge by itself |
| `connect_pins!` | `IdealConnectionRelation` | Accepts discrete endpoints only |
| `couple_capacitive!` | additive `CapacitiveCouplingRelation` | Creates a relation; finalization emits the capacitor row |
| `couple_inductive!` | additive `InductiveCouplingRelation` | Future relation; finalization emits the inductive branch when implemented |
| `coupled_window!` | replacement `CoupledWindowRelation` | Creates a relation; finalization emits the MTL rows |
| `coupled_window_spec_from_even_odd` | `CoupledWindowSpec` construction helper | Produces relation-owned MTL parameters; must not mutate line components |
| `sweep_component` | component-owned `SweepAxis` | Must preserve component parameter ownership |
| `sweep_relation` | relation-owned `SweepAxis` | Must preserve relation parameter ownership |
| `sweep_parameters` | linked multi-parameter `SweepAxis` | Must represent tied assignments explicitly |
| `sweep_plan` | `SweepPlan` | Combines axes by Cartesian product |
| `run_design_sweep` | semantic sweep runner | Applies points non-destructively and passes artifacts to evaluator |
| `finalize_circuit` | non-destructive finalization artifact | Returns netlist, provenance, node map, and segmentation plan |

## Component Authoring Contract

Every reusable component should document these fields.

| Field | Meaning |
| --- | --- |
| `id` | Stable semantic identity inside a draft |
| `prefix` | Stable generated-name namespace |
| `kind` | Component type, for example `:lc_resonator`, `:cpw_line`, `:qwr`, `:tunable_coupler` |
| `intrinsic_parameters` | Component-owned parameters such as length, capacitance, inductance, base RLGC, section count |
| `pins` | Public discrete connection endpoints |
| `anchors` | Public semantic references such as taps, spans, port annotations, or ground conventions |
| `owned_lines` | Abstract distributed lines owned by the component |
| `ground_convention` | Single-ended, floating, differential, or component-specific reference model |
| `allowed_couplings` | Local capability declarations |
| `lowering_rule` | How to lower the component's uncoupled local structure |
| `validation_rule` | Local metadata and parameter validation |
| `provenance_rule` | How generated primitive rows map back to component roles |

Implementation template:

```julia
struct MyComponent <: AbstractReusableComponent
    id::String
    prefix::String
    # typed intrinsic parameters
end

component_kind(component::MyComponent) = :my_component
component_pins(component::MyComponent) = [:plus, :minus]
component_parameter_snapshot(component::MyComponent) = Dict(:my_parameter => component.my_parameter)
validate_component(component::MyComponent) = ...
lower_component!(netlist, provenance, component::MyComponent, draft, resolve_node) = ...
```

Framework v1 now requires concrete component subtypes for reusable components. Do not add new reusable components as untyped dictionaries.

## Pin and Anchor Semantics

### `Pin`

`Pin` is a discrete electrical endpoint. Use it for lumped resonators, pads, terminals, and ideal node equivalence.

### `LineTap`

`LineTap` is a semantic position on an abstract distributed line.

```julia
LineTap(line_id="qwr_main", position=0.25, mode=:fraction)
LineTap(line_id="bus_a", position=320e-6, mode=:absolute)
```

It is not a physical discontinuity until a relation uses it.

User facade rule:

```julia
tap(component, 0.25)       # fraction
tap_m(component, 320e-6)   # meters
```

### `LineSpan`

`LineSpan` is a semantic interval on an abstract distributed line.

```julia
section(readout, 0.30, 0.42)
section_m(readout, 300e-6, 420e-6)
section(purcell_filter, 0.15, 0.30)
```

It is appropriate for replacement relations such as MTL coupled windows.

### `PortAnchor` and `GroundAnchor`

`PortAnchor` is a simulation or measurement annotation. `GroundAnchor` is a reference convention annotation.

Only `Pin` and resolved `LineTap` endpoints are connectable discrete endpoints. `PortAnchor` and `GroundAnchor` must not become generic coupling endpoints unless a helper explicitly resolves them to pins.

## Composition Relation Contract

Every relation must declare its modification mode.

| Mode | Meaning | Example |
| --- | --- | --- |
| `additive` | Preserve component-owned structure and add primitive rows | lumped capacitive coupling |
| `segmentation-only` | Request line boundaries without adding coupling primitives | explicit measurement tap boundary |
| `replacement` | Replace component-owned distributed sections during finalization | coupled MTL window |
| `annotation-only` | Add simulation or metadata semantics | measurement port annotation |

Every helper contract must document:

- accepted endpoint types
- created relation kind
- created segmentation requests
- modification mode
- parameter owner
- immediate validation
- deferred finalization validation
- primitive-level effect after finalization

### `connect_pins!`

`connect_pins!` means ideal node equivalence between compatible discrete pins.

It does not mean:

- capacitive coupling
- inductive coupling
- distributed MTL coupling
- line span replacement
- measurement port creation

### `couple_capacitive!`

```text
Accepted endpoints:
- PinRef
- LineTapRef

Creates:
- CapacitiveCouplingRelation

Modification mode:
- additive

May create:
- SegmentationRequest when an endpoint is LineTap

Does not:
- emit a C row immediately
- split a distributed line immediately
- access private internal nodes

Primitive-level effect:
- one C row between resolved endpoint nodes
```

### `couple_inductive!`

```text
Accepted endpoints:
- PinRef
- resolved line tap endpoint when explicitly supported

Creates:
- InductiveCouplingRelation

Modification mode:
- additive

Primitive-level effect:
- one L row or backend-supported inductive branch between resolved endpoints
```

### `add_mutual_inductive_coupling!`

```text
Accepted endpoints:
- Explicit inductor semantic references

Creates:
- MutualInductiveCouplingRelation

Modification mode:
- additive

Primitive-level effect:
- one K row referencing two resolved inductor primitive names
```

JosephsonCircuits `K` rows reference inductor element names instead of node names, so this relation requires stricter provenance.

### `add_line_tap!`

`LineTap` itself is only an anchor. `add_line_tap!` records actual usage of that anchor.

```text
Accepted endpoint:
- LineTapRef

Creates:
- LineTapRelation or a relation-specific tap dependency

Modification mode:
- segmentation-only, or segmentation-only + additive when combined with a coupling helper

Primitive-level effect:
- inserted boundary node only if a relation requires a primitive endpoint
```

### `coupled_window!`

```text
Accepted endpoints:
- LineSpanRef
- LineSpanRef

Creates:
- CoupledWindowRelation

Modification mode:
- replacement

Creates:
- SegmentationRequest on both lines at span boundaries

Does not:
- directly mutate CPW component chunks
- immediately emit MTL rows
- assume private node names

Primitive-level effect:
- original independent line chunks inside the spans are replaced by coupled MTL section rows
```

## Parameter Ownership

Components own intrinsic parameters. Relations own interaction parameters. Finalization resolves how those parameter sets combine, but must not silently change them.

| Parameter | Owner |
| --- | --- |
| resonator length | component |
| CPW base `L/C/R/G` per length | component |
| uncoupled section density | component |
| coupled window start/stop | relation |
| even/odd mode parameters | relation |
| tap capacitance | relation |
| tunable coupler frequency | coupler component |
| qubit-to-bus coupling capacitor | relation |

Sweep targets must preserve this ownership:

```julia
sweep_component("qwr1", :length_m, range(...))
sweep_relation("rel_qwr_bus_window", :window_length_m, range(...))
sweep_relation("rel_q1_coupler", :capacitance_f, range(...))
```

Use `sweep_parameters` for one axis that changes multiple owned parameters together.

```julia
sweep_parameters(
    [
        component_parameter("q1", :C_f) => (value -> value),
        component_parameter("q2", :C_f) => (value -> value * 1.1),
        relation_parameter("rel_q1_bus", :capacitance_f) => (value -> value * 0.02),
    ];
    values=range(...),
    label="linked capacitance family",
    unit="F",
)
```

Multiple axes in `sweep_plan(axis1, axis2, ...)` form a Cartesian product. Linked assignments inside one axis do not form a Cartesian product with each other; they move together at the same coordinate.

## Semantic Sweep Contract

The semantic sweep layer belongs to the framework-facing Julia core. It is separate from study-specific config sweeps.

| Type / helper | Responsibility |
| --- | --- |
| `ComponentParameterTarget` | Points to one component-owned parameter |
| `RelationParameterTarget` | Points to one relation-owned parameter |
| `SweepAssignment` | Assigns one value to one target |
| `SweepAxis` | Owns one list of sweep coordinates; each coordinate may contain one or more assignments |
| `SweepPlan` | Combines axes by Cartesian product |
| `SweepPoint` | Materializes assignments and metadata for one Cartesian point |
| `apply_sweep_point` | Returns a patched draft without mutating the original |
| `run_design_sweep` | Finalizes every point and passes `(patched_draft, artifact, point)` to an evaluator |

Validation rules:

- Unknown component/relation targets must fail before or during point application.
- Invalid patched parameters must raise `FrameworkValidationError`.
- `on_error=:throw` must stop at the first invalid point.
- `on_error=:record` must return a failed row with error metadata.
- Evaluators must not mutate the original draft.

## Distributed Line Segmentation

Distributed lines are abstract until finalization.

```julia
LineSpec(
    line_id="qwr_main",
    length_m=5.2e-3,
    base_sections=100,
    boundary_conditions=(left=:open, right=:short),
)
```

Relations create declarative requests:

```julia
SegmentationRequest(
    line_id="qwr_main",
    positions=[0.25, 0.40],
    reason=:coupled_window,
    relation_id="rel_qwr_bus_window",
)
```

The relation owns the reason for segmentation. The draft/finalization owns the merged segmentation plan.

### Conflict Policy

v1 supports:

- multiple non-overlapping replacement spans on one line
- additive lumped coupling at tap points outside replacement spans
- span-to-span coupled windows between compatible `LineSpan` anchors

v1 does not support:

- overlapping coupled-window replacement spans on the same line
- nested replacement relations
- tap insertion inside a replaced MTL span unless the replacement relation explicitly documents how to resolve it
- helper-order-dependent segmentation behavior

Coordinate snapping policy must be explicit. v1 should prefer either `:insert_boundary` or `:error`; it must not silently move relation endpoints.

## Finalization Pipeline

Finalization is the only stage that resolves semantic intent into primitive rows.

Pipeline:

1. Validate local component metadata.
2. Validate global component and relation graph.
3. Validate endpoint compatibility.
4. Resolve pins and anchors.
5. Collect segmentation requests.
6. Merge segmentation requests into an order-independent segmentation plan.
7. Detect relation conflicts.
8. Lower component-owned uncoupled chunks.
9. Lower composition relations according to modification mode.
10. Assign stable primitive node names.
11. Emit JosephsonCircuits-compatible flat netlist.
12. Emit provenance, node map, and segmentation map.

Finalization does not own:

- choosing physical design intent
- changing component intrinsic parameters
- silently modifying relation parameters
- inferring missing coupling models
- performing FEM or layout extraction

## Provenance

Every generated primitive row should be traceable back to a component, a relation, or both.

```julia
Provenance(
    row_index=17,
    primitive_kind=:L,
    component_id="qwr1",
    relation_id="rel_qwr_bus_window",
    source=:finalization,
    role=:relation_mtl_self_L,
    semantic_path=["qwr1", "main_line", "chunk_003"],
    segment_id="rel_qwr_bus_window",
    parameter_owner=:relation,
    parameter_snapshot=Dict(:length_m => 100e-6),
    generated_name="L_qwr1_main_003",
)
```

Implementation uses `ProvenanceRecord` with `component_ids::Vector{String}` rather than a single component id, because replacement relations such as MTL windows are generated from two components.

Recommended role vocabulary:

- `component_self_lumped`
- `component_distributed_self_L`
- `component_distributed_self_C`
- `relation_lumped_coupling_C`
- `relation_lumped_coupling_L`
- `relation_mutual_K`
- `relation_mtl_self_L`
- `relation_mtl_self_C`
- `relation_mtl_cross_C`
- `relation_port`
- `segmentation_artifact`

Provenance is diagnostic metadata, not physical semantics.

Minimum required fields:

- `row_index`
- `generated_name`
- `primitive_kind`
- `component_ids`
- `relation_id`
- `role`
- `semantic_path`
- `segment_id`
- `parameter_owner`
- `parameter_snapshot`

## Implementation Path

Framework v1 is a breaking-change sandbox implementation. Do not preserve old authoring helpers as compatibility wrappers.

| Category | Items |
| --- | --- |
| Preserve | `RLGCSpec`, `CoupledWindowSpec`, distributed segment emission, coupled-window row emission |
| Replace | old draft authoring helpers with concrete component subtypes, `pin`, `tap`, `tap_m`, `section`, `section_m`, `connect_pins!`, `couple_capacitive!`, `coupled_window!`, and `finalize_circuit` |
| Remove from user API | direct primitive authoring, private node lookup, old connect/window/finalize helper names |
| Current v1 patch | hard validation, richer provenance, semantic multi-parameter sweep |
| Add later | generic inductive relations, richer port/ground annotations, additional component library entries requested by a concrete design |
| Not v1 | `core` migration, UI/API schema migration, layout-driven anchor extraction, FEM/GDS parameter extraction, symbolic quantization, non-JosephsonCircuits solver backend |

## Implementation Review Checklist

Reject or revise a future helper if it:

- emits primitive rows before finalization
- assumes private internal node names
- mutates component-owned lines directly
- uses `LineSpanRef` as an endpoint for `connect_pins!`
- creates helper-order-dependent segmentation
- silently changes component or relation parameters
- lacks a relation modification mode
- cannot describe primitive-level provenance

Accept a future helper only if it documents:

- endpoint types
- relation kind
- parameter ownership
- segmentation requests
- modification mode
- validation timing
- finalization behavior
- expected primitive-level effect

## AI Agent Authoring Playbooks

These playbooks are intended to become Codex or other AI Agent skills. They are written as implementation-facing rules, not user tutorials.

### Build Reusable Circuit Component

When an agent is asked to add a reusable component:

1. Create a concrete subtype of `AbstractReusableComponent`.
2. Store intrinsic parameters as typed fields, not an unstructured parameter dictionary.
3. Implement `component_kind`, `component_pins`, `component_anchors` when needed, `component_parameter_snapshot`, `validate_component`, `allowed_couplings`, `ground_convention`, and `lower_component!`.
4. Expose a user facade constructor such as `my_component!(draft, id; kwargs...)`.
5. Register the component through the draft registration path so duplicate id and prefix checks run.
6. Add smoke tests for constructor type, validation errors, finalization rows, and provenance.
7. Update Learn only if the component is part of a user-facing recipe.

The agent must not:

- add a reusable component as a generic dictionary
- expose private generated nodes as public pins
- emit primitive rows from the constructor
- bypass provenance for rows emitted during lowering

### Assemble Circuit Components

When an agent is asked to assemble a circuit:

1. Identify component declarations first.
2. Identify public endpoints with `pin`, `tap`, `tap_m`, `section`, or `section_m`.
3. Add relations with `connect_pins!`, `couple_capacitive!`, `coupled_window!`, or a documented relation helper.
4. Use `sweep_component`, `sweep_relation`, and `sweep_parameters` for parameter studies.
5. Finalize with `finalize_circuit` or evaluate with `run_design_sweep`.
6. Inspect `provenance_table` to explain generated rows.

The agent must not:

- manually connect to `*_boundary*`, `*_n*`, or other generated internal nodes
- manually split CPW/QWR lines before using a relation helper
- use `connect_pins!` as a stand-in for physical coupling
- hide design parameters in evaluator closures when a semantic sweep target can represent them
