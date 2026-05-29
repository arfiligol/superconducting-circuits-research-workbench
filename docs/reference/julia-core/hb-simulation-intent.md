---
aliases:
  - HB Simulation Intent
  - Harmonic Balance Simulation Intent
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Defines how CircuitPlan declares HB ports, source slots, pump axes, observables, and solver-facing intent.
version: v1.5.0
last_updated: 2026-05-29
updated_by: codex
---

# HB Simulation Intent

HB simulation intent is the CircuitPlan-level contract for harmonic-balance simulation. It declares external ports, pump axes, source slots, observable requests, and solver-facing defaults before Runner execution sees runtime values.

The core rule is:

```text
CircuitPlan declares simulation intent.
Compiler validates simulation intent against the compiled circuit.
Runner binds runtime values and executes the validated HB problem.
```

## Conceptual Pipeline

```text
CircuitPlan
  -> ExternalPort declarations
  -> HBIntent declarations
  -> compile_to_josephson
  -> JosephsonCompiledCircuit
  -> HBProblemSpec
  -> run_hb_problem / run_frequency_sweep
```

CircuitPlan declares what is allowed. The compiler validates and maps that intent into the compiled circuit. The Runner binds task runtime values to the validated slots. JosephsonCircuits.jl receives normalized netlist rows, component values, sources, frequencies, harmonic counts, and whitelisted solver controls.

!!! warning "Runner does not own HB semantics"
    Runner task payloads may choose runtime values, but they must not invent ports, source slots, pump axes, mode tuples, or observable meanings after compilation.

## Product-Aligned HB Path

`HBProblemSpec` is the normalized execution shape for product-aligned Core and Runner execution.

| Stage | Responsibility |
| --- | --- |
| `HBIntent` | declares ports, pump axes, source slots, observables, and default controls on the `CircuitPlan` |
| `HBRunSpec` | carries runtime values such as frequency sweep, pump frequencies, `source_currents`, and optional whitelisted kwargs |
| `build_hb_problem` | validates compiled intent against runtime values and creates `HBProblemSpec` |
| `HBProblemSpec` | executable problem spec carrying the compiled circuit handoff, netlist values, normalized `ws`, `wp`, `sources`, harmonics, controls, observables, and kwargs |
| `run_hb_problem` | executes the validated problem through the product-aligned HB entry point |

Low-level `run_hbsolve` is a JosephsonCircuits-facing adapter name. It must not contradict the product path or become the tutorial/Runner handoff when `HBProblemSpec` is available.

## HBProblemSpec Execution Contract

`HBProblemSpec` is the executable handoff between compilation and HB execution. It should contain, or carry a stable reference to, the compiled circuit and the exact solver inputs derived from it:

| Field family | Contract |
| --- | --- |
| compiled circuit handoff | compiled `JosephsonCompiledCircuit` identity, netlist rows, component values, port map, source-slot map, and observable map |
| frequencies | normalized angular `ws` from positive sweep frequencies in hertz |
| pumps | normalized angular `wp` from declared pump-axis bindings |
| sources | JosephsonCircuits source entries derived from declared `HBSourceSlot` records and `source_currents` |
| harmonics | `Nmodulationharmonics` and `Npumpharmonics` normalized to tuple shape |
| controls | typed `HBSolverControls` selected by the plan intent and runtime profile |
| observables | declared output requests for S/Z/QE/QEideal/CM extraction |
| kwargs | whitelisted optional HB kwargs recorded for provenance |

Runner code should pass `HBProblemSpec` to `run_hb_problem`; it should not reassemble a separate `hbsolve` call from task payload fields.

## ExternalPort

`ExternalPort` is the plan-level declaration for a physical or logical external port that may lower to JosephsonCircuits port rows.

Conceptual shape:

```julia
ExternalPort(
    id,
    index,
    endpoint,
    resistance_ohm,
    role,
)
```

| Field | Meaning |
| --- | --- |
| `id` | stable logical port name, such as `:signal_port`, `:pump_port`, or `:readout_port` |
| `index` | JosephsonCircuits port index |
| `endpoint` | CircuitPlan endpoint that lowers to a netlist node |
| `resistance_ohm` | reference / port resistance used when emitting port rows |
| `role` | semantic role such as `:signal`, `:pump`, `:readout`, `:dc_bias`, or `:mixed` |

Rules:

- port IDs must be unique;
- port indices must be unique;
- port endpoints must resolve during compile;
- external ports must lower to compatible JosephsonCircuits port rows;
- one physical port may support multiple source modes.

## PumpAxis

`PumpAxis` declares one independent pump-frequency axis in the HB problem.

Single pump:

```julia
PumpAxis(
    id = :pump,
    frequency_parameter = :pump_frequency,
)
```

Double pump:

```julia
PumpAxis(id = :pump_1, frequency_parameter = :pump_1_frequency)
PumpAxis(id = :pump_2, frequency_parameter = :pump_2_frequency)
```

Rules:

- the number of pump axes defines the HB mode tuple dimension;
- single-pump mode examples use tuples like `(1,)`;
- double-pump mode examples use tuples like `(1, 0)` and `(0, 1)`;
- DC mode `(0,)` must be explicitly allowed where relevant.

Runtime binding rules:

- every declared pump axis requires a pump-frequency binding;
- pump frequency values are in hertz at the user/API boundary;
- pump frequency values must be finite and positive;
- pump frequency remains required when the pump source current is `0.0`;
- circuit-family forbidden-frequency validation is a planned target with no recorded implementation date as of 2026-05-29.

## HBSourceSlot

`HBSourceSlot` declares a source slot that can be bound at runtime. The slot is part of the plan intent; the current value is a runtime binding.

Modeled large-signal source:

```julia
HBSourceSlot(
    id = :large_signal_in,
    role = :signal,
    port = :signal_port,
    mode = (1,),
    current_parameter = :large_signal_current,
)
```

Pump source:

```julia
HBSourceSlot(
    id = :pump_in,
    role = :pump,
    port = :pump_port,
    mode = (1,),
    current_parameter = :pump_current,
)
```

Double-pump source:

```julia
HBSourceSlot(
    id = :pump_1_in,
    role = :pump,
    port = :pump_port,
    mode = (1, 0),
    current_parameter = :pump_1_current,
)

HBSourceSlot(
    id = :pump_2_in,
    role = :pump,
    port = :pump_port,
    mode = (0, 1),
    current_parameter = :pump_2_current,
)
```

DC source:

```julia
HBSourceSlot(
    id = :dc_bias,
    role = :dc_bias,
    port = :pump_port,
    mode = (0,),
    current_parameter = :dc_current,
)
```

Runtime binding:

```julia
HBRunSpec(
    frequency_sweep = frequency_sweep,
    pump_frequencies = Dict(:pump => pump_frequency),
    source_currents = Dict(
        :dc_bias => dc_current,
        :pump_in => pump_current,
    ),
)
```

DC bias is not a separate binding family. It is an `HBSourceSlot` with `mode = (0,)`, bound through `source_currents`, and it requires `HBSolverControls(dc = true)`.

Rules:

- source slot IDs must be unique;
- source slot ports must reference existing `ExternalPort` declarations;
- source modes must be compatible with the declared pump axes;
- DC bias source slots must use `mode = (0,)`;
- DC bias current is bound through `source_currents[:dc_bias]`;
- `controls.dc = true` enables DC handling for DC source slots;
- `current = 0.0` is valid and means the source is intentionally off;
- source slot existence is not fake compute even if its current value is zero;
- source slot current value is a runtime binding.

## HBSourceSlot vs Linearized Probe

`HBSourceSlot` describes sources passed to JosephsonCircuits `sources`, such as pump drives, DC bias, or intentionally modeled large-signal drives.

Small-signal S-parameter probing is not automatically a source slot. It is normally declared through `HBObservableRequest` as an output/input mode-port extraction from the linearized solution.

A signal can be represented as an `HBSourceSlot` only when the circuit model intentionally treats it as a source in `sources`.

Source slot example:

```julia
HBSourceSlot(
    id = :pump_in,
    role = :pump,
    port = :pump_port,
    mode = (1,),
    current_parameter = :pump_current,
)
```

Linearized probe example:

```julia
SParameterRequest(
    id = :s11_signal,
    outputmode = (0,),
    outputport = :signal_port,
    inputmode = (0,),
    inputport = :signal_port,
)
```

!!! warning "Do not create probe sources"
    Do not create a source slot only because an S-parameter input port exists.

## HBObservableRequest

Observable requests declare what the caller may extract from solver output.

Signal reflection:

```julia
SParameterRequest(
    outputmode = (0,),
    outputport = :signal_port,
    inputmode = (0,),
    inputport = :signal_port,
)
```

Idler observable:

```julia
SParameterRequest(
    outputmode = (-1,),
    outputport = :signal_port,
    inputmode = (0,),
    inputport = :signal_port,
)
```

Output-family requests include:

```julia
SParameterRequest(...)
ZParameterRequest(...)
QERequest(...)
QEIdealRequest(...)
CMRequest(...)
```

Rules:

- observable ports must reference declared external ports;
- observable modes must be compatible with pump axes;
- unsupported observable families must fail clearly;
- requested S, Z, QE, QEideal, and CM families must be extracted from solver output when requested;
- Julia Core extraction is family-complete: if a family is requested, Core extracts the full requested family, while upper layers decide filtering, persistence, and display;
- if a requested output family is absent from the solver result, extraction must fail clearly instead of silently dropping the family;
- if an unrequested output family is absent from the solver result, extraction should ignore that absence;
- solver-returned `NaN` values are preserved and surfaced; Core must not create NaN-placeholder values for missing families;
- Runner result extraction should follow declared observables, not hardcoded S11 forever.

## HBIntent

`HBIntent` is the CircuitPlan-level simulation intent for harmonic-balance execution.

Conceptual shape:

```julia
HBIntent(
    pump_axes = [...],
    source_slots = [...],
    observables = [...],
    default_solver_controls = HBSolverControls(...),
)
```

Rules:

- `HBIntent` is related to topology, but not identical to topology;
- changing source current values does not change `HBIntent`;
- changing pump-axis dimension changes `HBIntent`;
- changing the number of source slots changes `HBIntent`;
- changing observable requests changes output intent.

## Product HB Profiles

Product HB profiles are named by runtime behavior, not by removing HB structure.

| Profile | Pump axis | Pump source slot | DC source slot | Runtime binding |
| --- | --- | --- | --- | --- |
| `:pump_off` | declared | declared | absent | `pump_current = 0.0` |
| `:pumped` | declared | declared | absent | `pump_current` may be nonzero |
| `:pumped_dc` | declared | declared | declared | `pump_current` plus `dc_current` |

Pump-off is an executable HB problem with a declared pump axis and source slot. It is not an empty-pump product path.

Shared pump-off / pumped declaration:

```julia
hb_intent!(
    plan;
    pump_axes = [
        PumpAxis(id = :pump, frequency_parameter = :pump_frequency),
    ],
    source_slots = [
        HBSourceSlot(
            id = :pump_in,
            role = :pump,
            port = :pump_port,
            mode = (1,),
            current_parameter = :pump_current,
        ),
    ],
    observables = [
        SParameterRequest(
            id = :s11_signal,
            outputmode = (0,),
            outputport = :signal_port,
            inputmode = (0,),
            inputport = :signal_port,
        ),
    ],
    default_solver_controls = HBSolverControls(
        n_pump_harmonics = 16,
        n_modulation_harmonics = 8,
        returnS = true,
        returnZ = true,
        returnQE = true,
        returnCM = true,
    ),
)
```

Pump-off runtime binding:

```julia
HBRunSpec(
    frequency_sweep = frequency_sweep,
    pump_frequencies = Dict(:pump => pump_frequency),
    source_currents = Dict(:pump_in => 0.0),
)
```

Rules:

- `:pump_off` keeps the same pump axis and source slot as `:pumped`;
- `pump_frequency` is required, finite, and positive for all three profiles;
- `pump_current = 0.0` is the source-off binding for `:pump_off`;
- product HB code must not model pump-off by deleting pump axes or source slots;
- S/Z/QE/QEideal/CM outputs may be requested when the selected solver path supports them.

## Key Separation

Julia Core uses separate keys for topology, HB intent, HB problem shape, and concrete runtime values.

```text
topology_key
hb_intent_key
hb_problem_shape_key
run_value_key
```

### topology_key

`topology_key` includes:

- component hierarchy;
- component types;
- relations;
- endpoint topology;
- external ports that emit netlist rows;
- structural parameters affecting emitted rows;
- line taps / spans / distributed segmentation.

### hb_intent_key

`hb_intent_key` includes:

- pump-axis declarations;
- source slot declarations;
- source roles;
- mode tuple declarations;
- observable request declarations;
- solver-control families allowed by the intent.

### hb_problem_shape_key

`hb_problem_shape_key` includes:

- harmonic counts;
- `returnS` / `returnZ` / `returnQE` / `returnCM`;
- requested S/Z/QE/QEideal/CM result-family set;
- `keyedarrays`;
- `sorting` if it changes output shape or indexing assumptions;
- mode truncation controls;
- optional kwargs that change solver problem structure.

### run_value_key

`run_value_key` includes:

- concrete frequency arrays;
- concrete pump-frequency values;
- concrete source current values;
- `current = 0.0` source-off bindings;
- numeric solver tolerances that do not alter problem shape;
- output slicing / display preferences.

| Change | topology_key | hb_intent_key | hb_problem_shape_key | run_value_key |
| --- | ---: | ---: | ---: | ---: |
| pump current nonzero to `0.0` | unchanged | unchanged | unchanged | changed |
| pump frequency value changes | unchanged | unchanged | unchanged | changed |
| add second pump axis | unchanged unless circuit changes | changed | changed | changed |
| change `n_pump_harmonics` | unchanged | unchanged | changed | changed |
| change `n_modulation_harmonics` | unchanged | unchanged unless modulation basis changes | changed | changed |
| change requested S/Z/QE/QEideal/CM families | unchanged | unchanged | changed | changed |
| change `maxintermodorder` | unchanged | unchanged | changed | changed |
| change nonlinear tolerance `ftol` | unchanged | unchanged | unchanged | changed |
| add idler observable | unchanged | changed | may change | changed |
| add new physical port | changed | changed | changed | changed |
| change line-tap position | changed | may change | may change | changed |
| change frequency sweep range | unchanged | unchanged | unchanged | changed |

In the MVP key model, result-family flags such as `returnS`, `returnZ`, `returnQE`, and `returnCM` are grouped under `hb_problem_shape_key` because they affect requested solver outputs and cache compatibility, even if they do not always change the nonlinear solve itself. `QEideal` is part of the requested result-family set and must be extracted or reported as absent whenever the solver result does not contain it.

## Validation Boundary

HB validation is split across compile time and run time.

### Compile-Time Validation

`compile_to_josephson(plan)` validates:

- external port endpoints resolve;
- port indices are unique;
- source slots reference existing ports;
- source mode tuples match pump-axis dimension;
- DC mode usage is explicitly allowed;
- observable requests reference existing ports;
- observable modes are compatible;
- compiled output contains enough port metadata for HB problem construction.

### Run-Time Validation

`build_hb_problem(compiled, run_spec)` validates:

- frequency sweep values are positive;
- pump frequency values are finite and positive;
- pump frequency bindings exist even when a pump source current is `0.0`;
- pump harmonic tuple lengths match pump axis count;
- modulation harmonic tuple lengths match the declared modulation basis;
- source current values are present or have explicit defaults;
- DC current values are present in `source_currents` for declared DC source slots;
- `controls.dc = true` is set when an intent declares a DC bias source slot;
- `current = 0.0` is accepted;
- optional solver kwargs are whitelisted;
- requested observable families are enabled by the output-request configuration.
- `validate_output_request_configuration(compiled, hb_problem)` validates request configuration before solve.
- actual requested-family availability is checked after `hbsolve` output returns.

## Output Request Configuration And Extraction

Default requested outputs are S, Z, QE, QEideal, and CM. Julia Core validates the requested output configuration before solve, then validates actual requested-family availability after `hbsolve` output returns.

Pre-solve validation checks whether the request is internally consistent with the compiled circuit, observable declarations, and solver controls. It does not prove that JosephsonCircuits.jl will return every requested family.

Target API:

```julia
output_request_report = validate_output_request_configuration(compiled, hb_problem)
```

| Output | Requested default | Validation behavior |
| --- | ---: | --- |
| S | true | request only when enabled; post-solve extraction fails if requested family is absent |
| Z | true | request only when enabled; post-solve extraction fails if requested family is absent |
| QE | true | request only when enabled; post-solve extraction fails if requested family is absent |
| QEideal | true when QE-family extraction is requested | request with QE-family extraction; post-solve extraction fails if absent from solver output |
| CM | true | request only when enabled; post-solve extraction fails if requested family is absent |

Julia Core and Runner must not silently drop requested output families or reduce a run to S-only output. Requested-family absence after solver execution is an extraction failure, not an empty trace set.

Extraction is family-complete. If S, Z, QE, QEideal, or CM is requested, Julia Core extracts the full requested family from the solver result. Upper layers handle filtering, persistence, and display decisions.

Missing-output and `NaN` policy:

- missing requested family: fail clearly and name the missing family / observable;
- missing unrequested family: allowed;
- solver-returned `NaN`: preserve and surface the value;
- missing family: never create NaN-placeholder values.

## Implementation Status

This page is stable as the target source of truth. It is not claiming that every concept is already implemented.

| Concept | Target contract | Current implementation | Status |
| --- | --- | --- | --- |
| `ExternalPort` | first-class CircuitPlan declaration | MVP struct and `external_port!` path exist | design-stable |
| `HBIntent` | first-class plan-level intent | MVP struct and `hb_intent!` path exist | design-stable |
| `HBSourceSlot` | first-class source slot declaration | MVP struct exists; DC mode validation is part of compile validation | design-stable |
| `HBObservableRequest` | first-class observable declaration | current Runner extraction still MVP / trace-specific | target |
| `HBSolverControls` | typed first-class controls | current Runner only partially maps controls | target |
| `optional_hb_kwargs` | whitelist only | not fully implemented | target |
| `HBProblemSpec` | executable HB execution shape carrying compiled circuit handoff, netlist values, normalized solver inputs, controls, observables, and kwargs | MVP struct carries compiled circuit plus normalized solver inputs | design-stable |
| `run_hb_problem` | product-aligned HB execution entry | executable target API for HBProblemSpec | design-stable |
| `current = 0.0` | valid source-off runtime binding | should be accepted | design-stable |

## Related

- [JosephsonCircuits hbsolve Controls](josephsoncircuits-hbsolve-controls.md)
- [Compiler](compiler.md)
- [Compiled Circuit](compiled-circuit.md)
- [Runner-Safe API](runner-safe-api.md)
