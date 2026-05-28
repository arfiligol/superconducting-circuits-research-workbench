---
aliases:
  - Julia Core Parameter Sweeps
  - Sweep Architecture
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Defines the Julia Core parameter sweep execution architecture.
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Parameter Sweeps

Parameter Sweep is a first-class execution model in Julia Core.

A sweep explores a set of parameter points while preserving the distinction between:

```text
- parameters that change topology / compiler lowering;
- parameters that only change numeric values;
- parameters that change source / drive / analysis settings.
```

The sweep engine should avoid unnecessary compilation. If the circuit topology is unchanged, the compiled circuit should be reused and only numeric bindings should change.

Parameter Sweep is not just a serial `for` loop. It is modeled as parameter classification, topology grouping, compile policy selection, execution backend selection, and result collection.

The key question for every sweep axis is:

```text
Does this parameter change the CircuitPlan topology or compiler result?
```

If yes, it is structural. If no, it is numeric or runtime-bindable.

## Sweep Architecture

```text
Component Library plan builder
        |
        v
Parameterized CircuitPlan
        |
        v
SweepSpec
        |
        v
Parameter classification
        |
        v
Topology grouping / compile key
        |
        v
Compile policy
        |
        v
Execution backend
        |
        v
SweepResult
```

The sweep engine should support Pluto and Julia Runner through the same Julia Core API. Pluto may call the sweep engine for explicit batch sweeps. The Runner may call the same sweep engine for deterministic platform tasks.

## Parameter Roles

Parameter roles are part of the Julia Core sweep architecture.

```text
StructuralParameter
    changes CircuitPlan topology or compiler lowering result

NumericParameter
    changes numeric values only, without changing topology

DriveParameter
    changes drive / source / pump settings

AnalysisParameter
    changes post-processing / fitting / result extraction settings
```

| Parameter | Role | Reason |
| --- | --- | --- |
| `qwr_length` | structural | May change line discretization, nodes, breakpoints, or section count |
| `n_sections` | structural | Changes target netlist size and topology |
| `line_tap_position` | structural | Changes breakpoint insertion and node map |
| `line_span_start_stop` | structural | Changes distributed coupling region |
| `boundary = :open / :short` | structural | Changes circuit connection topology |
| `component_type = LinearInductor / SQUID` | structural | Changes component hierarchy and lowering |
| `capacitance_value` | numeric | Changes value binding only |
| `inductance_value` | numeric | Changes value binding only |
| `coupling_capacitance` | numeric if endpoints unchanged | Changes value only if the coupling relation already exists |
| `junction_Ic` | numeric if junction topology unchanged | Changes nonlinear element parameter only |
| `external_flux` | numeric or drive-like | Changes parameter binding, not topology |
| `pump_frequency` | drive | Changes solver input / source setting |
| `pump_amplitude` | drive | Changes solver input / source setting |
| `fit_window` | analysis | Changes post-processing only |

## Structural Sweep

Structural sweeps change topology or compiler lowering result.

Examples:

```text
- line length affects line segmentation;
- tap location changes inserted breakpoints;
- coupled-window span changes distributed coupling region;
- component type changes from linear inductor to SQUID;
- boundary condition changes from open to short.
```

Structural sweep execution:

```text
for each structural point or topology group:
    build CircuitPlan
    validate_authoring(plan)
    compiled = compile_to_josephson(plan)
    run simulation
    collect result
```

Structural sweeps should use parallel execution whenever points are independent.

At minimum, Julia Core supports these executor concepts:

```text
SerialExecutor
ThreadedExecutor
RunnerExecutor
```

The architecture also allows future extension to:

```text
DistributedExecutor
HPCExecutor
```

The design should prefer `ThreadedExecutor` or another parallel executor when sweep points are independent and the user requests hardware utilization.

## Numeric Sweep

Numeric sweeps do not change topology or compiler lowering result.

Numeric sweep execution:

```text
plan = build_plan(template_parameters)
validate_authoring(plan)
compiled = compile_to_josephson(plan)

for each numeric point:
    bound = bind_numeric_parameters(compiled, numeric_point)
    run simulation
    collect result
```

The compiled circuit should be reused.

The sweep engine should not recompile for each numeric point unless:

```text
- parameter classification is unknown;
- binding fails;
- the compiler reports the parameter affects topology;
- the user explicitly requests compile-per-point for debugging.
```

Numeric sweeps should still use Julia parallel execution when points are independent.

The baseline numeric sweep path is:

```text
compile once
        |
        v
bind numeric values repeatedly
        |
        v
run with Julia CPU / Julia threaded execution
```

## Hybrid Sweep

Hybrid sweeps contain both structural and numeric axes.

Example:

```text
qwr_length       structural
coupling_fF      numeric
flux_phi0        numeric
pump_power       drive
```

Hybrid sweep execution should group points by topology key:

```text
for each topology_key:
    build representative CircuitPlan
    compiled = compile_to_josephson(plan)

    for each numeric / drive / analysis point inside the group:
        bind values
        run simulation or analysis
        collect result
```

Example conceptual API:

```julia
sweep = SweepSpec(
    axes = (
        qwr_length = StructuralAxis([4.8mm, 5.0mm, 5.2mm]),
        coupling_fF = NumericAxis(range(1.0, 10.0, length = 50)),
        flux_phi0 = NumericAxis(range(-0.5, 0.5, length = 101)),
    ),
    compile_policy = CompileByTopologyKey(),
    executor = ThreadedExecutor(),
)
```

Expected behavior:

```text
qwr_length = 4.8 mm
    compile once
    sweep coupling_fF x flux_phi0 numerically

qwr_length = 5.0 mm
    compile once
    sweep coupling_fF x flux_phi0 numerically

qwr_length = 5.2 mm
    compile once
    sweep coupling_fF x flux_phi0 numerically
```

## Compile Policy

Compile policies define when the sweep engine may reuse a compiled circuit.

```text
CompileEveryPoint
    compile every sweep point;
    safest but slowest;
    useful for debugging or fully structural sweeps.

CompileOnce
    compile one representative plan;
    valid only when all sweep axes are numeric / drive / analysis and topology is unchanged.

CompileByTopologyKey
    group sweep points by compile-equivalence key;
    compile once per group;
    preferred default for hybrid sweeps.
```

The preferred default is:

```text
CompileByTopologyKey
```

`CompileByTopologyKey` handles structural, numeric, and hybrid sweeps without unnecessary recompilation.

## Topology Key / Compile Equivalence

A topology key is the identity of everything that affects compiler output.

A topology key should include:

```text
- component hierarchy;
- component types;
- endpoint topology;
- line references;
- line taps;
- line spans;
- boundary choices;
- number of sections;
- distributed coupling geometry;
- any parameter that changes emitted target rows, node map, component map, or line_tap_map.
```

A topology key should exclude:

```text
- numeric values that only bind into existing target rows;
- drive amplitudes and frequencies if they do not alter compiled topology;
- post-processing settings.
```

If two sweep points have the same topology key, they can share the same `JosephsonCompiledCircuit`.

If two sweep points have different topology keys, they must not share compiled output.

Compile equivalence is therefore stronger than matching user-facing parameter names. It means the compiler would emit the same target structure, maps, and endpoint lowering result for both points.

## Parameter Classification

The sweep system should not rely only on user labels.

Parameter classification is part user-declared and part compiler-verifiable.

```text
User declares parameter role:
    structural / numeric / drive / analysis

Compiler validates whether the role is consistent:
    numeric parameter must not change topology key
    structural parameter may change topology key
```

If a user declares a parameter numeric but it changes the topology key, the sweep engine must fail or reclassify according to strictness policy.

Supported strictness policies:

```text
StrictSweepClassification
    error if declared role disagrees with compiler result

PermissiveSweepClassification
    warn and promote numeric parameter to structural

DebugSweepClassification
    compile every point and report inferred roles
```

The recommended default is:

```text
StrictSweepClassification
```

Strict classification is the default for reproducible research and Runner execution.

## Execution Backends

Execution backends are part of the final sweep architecture.

```text
SerialExecutor
    deterministic single-thread execution

ThreadedExecutor
    local Julia multi-threaded execution over independent sweep points

RunnerExecutor
    Julia Runner task execution path for product / platform tasks

DistributedExecutor
    optional local multi-process execution

HPCExecutor
    optional future cluster / job-array execution
```

If independent sweep points can be parallelized with Julia parallel execution, the sweep engine should support doing so.

For local research, `ThreadedExecutor` should be the default performance-oriented executor when the user requests hardware utilization and the sweep points are independent.

Serial execution is mainly for debugging, deterministic traceability, and small sweeps.

## Parallelism Rule

Parameter sweeps are performance-sensitive.

If sweep points are independent and no shared mutable state prevents parallel execution, Julia Core should support parallel execution using Julia's native parallel mechanisms.

At minimum, local threaded execution should be part of the sweep architecture.

The sweep engine should avoid unnecessary serialization of independent sweep points.

The implementation should expose executor selection rather than hiding all execution behind a serial `for` loop.

## Numeric Acceleration Backends

Numeric acceleration applies only to fixed-topology numeric sweep groups.

The final architecture includes optional acceleration hooks, but they must not replace the baseline Julia execution path.

```text
NumericAccelerationBackend
    None
    JAXSurrogateBackend
    JuliaGPUKernelBackend
```

Baseline:

```text
None
    compile once
    bind numeric values
    run with Julia CPU / ThreadedExecutor
```

Optional backends:

```text
JAXSurrogateBackend
    fixed-topology compact / surrogate model
    must be validated against HBSolver / JosephsonCircuits baseline
    must pass capability probe
    must respect validated parameter domain

JuliaGPUKernelBackend
    fixed-topology numeric kernel
    may use CUDA.jl, AMDGPU.jl, or Metal.jl depending on device and implementation
    must pass capability probe
    must validate against CPU / HBSolver baseline
```

!!! warning "Acceleration is not solver replacement"
    Numeric acceleration backends are optional fixed-topology acceleration paths.
    They do not automatically accelerate JosephsonCircuits.jl `hbsolve`.
    They may require compact models, surrogate models, or backend-specific numeric kernels.
    They must be validated against the baseline solver before being used for trusted sweeps.

## Capability Probe

Acceleration backends must use environment and capability checks.

Suggested API concept:

```julia
probe_acceleration(:jax)
probe_acceleration(:cuda)
probe_acceleration(:amdgpu)
probe_acceleration(:metal)
```

Suggested result concept:

```julia
AccelerationCapability(
    available = true,
    backend = :cuda,
    supports_complex = true,
    supports_float64 = true,
    device_name = "...",
    warnings = String[],
)
```

Acceleration selection should support policies:

```text
RequireAcceleration(:jax)
    error if unavailable

PreferAcceleration(:jax, fallback = JuliaThreadedBackend())
    use acceleration if valid, otherwise fallback

NoAcceleration()
    use baseline Julia execution
```

## Validation Requirement for Surrogate / Compact Backends

A surrogate or compact numeric backend may be used only after validation against the baseline HBSolver / JosephsonCircuits path.

The validation should check:

- selected validation parameter points;
- frequency grid or interpolation domain;
- error tolerance;
- parameter domain coverage;
- complex-valued S-parameter agreement when applicable.

If validation fails, the sweep must fall back to the baseline Julia execution path or fail according to user policy.

## Sweep Result

`SweepResult` is more than a raw list.

It should preserve:

```text
- sweep axes and roles;
- topology keys;
- compile policy used;
- executor used;
- acceleration backend used;
- per-point success / failure;
- per-point compile status;
- per-point simulation status;
- compiled-circuit references or hashes;
- result traces / summaries;
- warnings;
- provenance.
```

This is essential for debugging and performance analysis.

## Pluto Usage

Pluto should use the same sweep architecture.

Two Pluto modes are supported:

```text
Reactive single-point exploration
    user changes parameters
    one plan is built
    one compiled circuit is produced
    one simulation is run

Explicit batch sweep
    user defines SweepSpec
    user intentionally runs a sweep
    sweep engine uses compile policy and executor
```

Pluto should not accidentally trigger large batch sweeps through reactive slider updates.

Recommended reactive single-point pattern:

```julia
params = (
    coupling_fF = 3.0,
    flux_phi0 = 0.1,
)

plan = build_plan(params)
compiled = compile_to_josephson(plan)
result = run_frequency_sweep(compiled, freqs)
```

Recommended explicit batch sweep pattern:

```julia
sweep = SweepSpec(
    axes = (
        coupling_fF = NumericAxis(range(1.0, 10.0, length = 50)),
        flux_phi0 = NumericAxis(range(-0.5, 0.5, length = 101)),
    ),
    compile_policy = CompileOnce(),
    executor = ThreadedExecutor(),
)

result = run_parameter_sweep(build_plan, sweep)
```

## Runner Usage

Runner should use the same sweep architecture.

Runner execution should not create a separate sweep model.

The Runner may map Backend task payloads into:

```text
Component Library plan builder
SweepSpec
CompilePolicy
Executor
AccelerationPolicy
```

The actual sweep logic should remain Julia Core logic.

Runner sweep tasks should call the Julia Core sweep engine. Runner adapters may map Backend payloads into `SweepSpec`, `CompilePolicy`, `Executor`, and `AccelerationPolicy`, but they must not implement a separate sweep execution model.
