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
version: v1.0.0
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
  -> run_hbsolve / run_frequency_sweep
```

CircuitPlan declares what is allowed. The compiler validates and maps that intent into the compiled circuit. The Runner binds task runtime values to the validated slots. JosephsonCircuits.jl receives normalized netlist rows, component values, sources, frequencies, harmonic counts, and whitelisted solver controls.

!!! warning "Runner does not own HB semantics"
    Runner task payloads may choose runtime values, but they must not invent ports, source slots, pump axes, mode tuples, or observable meanings after compilation.

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
    frequency_parameter = :pump_frequency_hz,
)
```

Double pump:

```julia
PumpAxis(id = :pump_1, frequency_parameter = :pump_1_frequency_hz)
PumpAxis(id = :pump_2, frequency_parameter = :pump_2_frequency_hz)
```

Rules:

- the number of pump axes defines the HB mode tuple dimension;
- single-pump mode examples use tuples like `(1,)`;
- double-pump mode examples use tuples like `(1, 0)` and `(0, 1)`;
- DC mode `(0,)` must be explicitly allowed where relevant.

## HBSourceSlot

`HBSourceSlot` declares a source slot that can be bound at runtime. The slot is part of the plan intent; the current value is a runtime binding.

Signal source:

```julia
HBSourceSlot(
    id = :signal_in,
    role = :signal,
    port = :signal_port,
    mode = (0,),
    current_parameter = :signal_current_a,
)
```

Pump source:

```julia
HBSourceSlot(
    id = :pump_in,
    role = :pump,
    port = :pump_port,
    mode = (1,),
    current_parameter = :pump_current_a,
)
```

Double-pump source:

```julia
HBSourceSlot(
    id = :pump_1_in,
    role = :pump,
    port = :pump_port,
    mode = (1, 0),
    current_parameter = :pump_1_current_a,
)

HBSourceSlot(
    id = :pump_2_in,
    role = :pump,
    port = :pump_port,
    mode = (0, 1),
    current_parameter = :pump_2_current_a,
)
```

DC source:

```julia
HBSourceSlot(
    id = :dc_bias,
    role = :dc_bias,
    port = :pump_port,
    mode = (0,),
    current_parameter = :dc_current_a,
)
```

Rules:

- source slot IDs must be unique;
- source slot ports must reference existing `ExternalPort` declarations;
- source modes must be compatible with the declared pump axes;
- `current = 0.0` is valid and means the source is intentionally off;
- source slot existence is not fake compute even if its current value is zero;
- source slot current value is a runtime binding.

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

Optional future observable families include:

```julia
QERequest(...)
QEIdealRequest(...)
CMRequest(...)
ZParameterRequest(...)
```

Rules:

- observable ports must reference declared external ports;
- observable modes must be compatible with pump axes;
- unsupported observable families must fail clearly;
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

## Key Separation

Julia Core uses separate keys for topology, HB intent, and concrete execution.

```text
topology_key
hb_intent_key
run_key
```

### topology_key

`topology_key` includes:

- component hierarchy;
- relations;
- ports that emit netlist rows;
- endpoint topology;
- structural parameters affecting emitted target rows.

### hb_intent_key

`hb_intent_key` includes:

- pump-axis dimension;
- source slot definitions;
- source roles;
- mode tuples;
- observable requests;
- solver control structure that changes HB problem shape.

### run_key

`run_key` includes:

- concrete frequency arrays;
- pump frequency values;
- source current values;
- harmonic counts;
- solver kwargs;
- output slicing options.

| Change | topology_key | hb_intent_key | run_key |
| --- | ---: | ---: | ---: |
| pump current from nonzero to `0.0` | unchanged | unchanged | changed |
| add second pump axis | unchanged or changed depending on circuit | changed | changed |
| add new physical port | changed | changed | changed |
| change frequency sweep range | unchanged | unchanged | changed |
| add idler observable | unchanged | changed | changed |
| change capacitance value | usually unchanged | unchanged | changed |
| change line-tap position | changed | may change | changed |

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
- pump frequency values are positive;
- harmonic tuple lengths match pump axis count;
- source current values are present or have explicit defaults;
- `current = 0.0` is accepted;
- optional solver kwargs are whitelisted;
- requested observables can be extracted from solver output.

## Related

- [JosephsonCircuits hbsolve Controls](josephsoncircuits-hbsolve-controls.md)
- [Compiler](compiler.md)
- [Compiled Circuit](compiled-circuit.md)
- [Runner-Safe API](runner-safe-api.md)
