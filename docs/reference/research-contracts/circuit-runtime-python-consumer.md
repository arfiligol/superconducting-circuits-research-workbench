---
aliases:
 - Circuit Workbench Runtime
 - Python circuit consumer
tags:
 - diataxis/reference
 - audience/team
 - sot/true
 - topic/research-contracts
status: stable
owner: docs-team
audience: team
scope: Stabilized staged-action contract plus the accepted live optimization-progress extension for the public Circuit Workbench runtime and Python-consumer boundary.
version: v1.2.0
last_updated: 2026-09-03
updated_by: codex
title: Circuit Runtime / Python Consumer
description: Stabilized contract for visible Python circuit plans, staged Julia actions, immutable receipts, and read-only result resolution, with an accepted live optimization-progress extension.
sidebar:
 label: Circuit Runtime / Python Consumer
 order: 45
---

# Circuit Runtime / Python Consumer

The visible `CircuitPlan`, `CircuitSim`, staged actions, source-bound
request/receipt schemas, and one-process Julia boundary are stabilized and
integrated as Workbench `6b6d13156bd3d5074b7da90baed6af10399765e7`;
the current base `d2f5c1936a3e0cee13fc9ec72d4f4b3b3037605d` contains that
identity. The live optimization-progress callback below is a scoped
`ACCEPTED / NOT_INTEGRATED` extension. It does not change the stabilized
plan, compiler, optimizer, staged-result, or receipt contracts.

## Ownership Boundary

| Owner | Owns |
| --- | --- |
| Workbench runtime | Public package and schemas; visible generic plan/compiler; named-coordinate propagation; node ordering and passivity checks; complete-complement Schur and physical-quantity extraction; stage execution; automatic identities; immutable receipts; generic result and report readers. |
| JosephsonCircuits.jl | Parse the compiled closed linear netlist and assemble the full-system numeric C/K/G matrices; execute the separate HB backend for S/Y/Z responses. |
| Consumer | Notebook source; plan assembly; consumer libraries; artifact declarations; targets, objective meaning, reduction, exact Human-authorized Gates, variables, optimizer controls, stage parameters, and run locations. |
| Host project / Human | Scientific meaning, Design Targets, Gate authority, acceptance, and decision history. |
| Layout and solver owners | Layout, geometry, materials, and solver artifacts supplied through sealed bindings. Workbench does not execute those solvers. |

Public examples remain with public consumers. Private plans, variables, targets,
objectives, identities, artifacts, and evidence remain with their private owner.

## Public Surface

The distribution is `superconducting-circuits-runtime`; its import name is
`superconducting_circuits_runtime`.

```python
from superconducting_circuits_runtime import (
    CircuitLibrary,
    CircuitObjective,
    CircuitPlan,
    CircuitSim,
    DirectEvaluationSpec,
    DirectSolveSpec,
    GateSpec,
    OptimizationProgress,
    OptimizerSpec,
    ReductionSpec,
    ResponseSpec,
    StandaloneDirectEvaluationSpec,
    T1Spec,
    VariableSpec,
    circuit_component,
    resolve_circuit_campaign,
    resolve_circuit_result,
)
```

`CircuitPlan` remains the sole complete-plan container. It owns visible
topology, parameters, connections, ports, and inspectable engineering and
schematic intent. A `@circuit_component` factory may compose registered types,
but it must seal a graph before Julia starts; it is never a candidate-evaluation
callback. `CircuitPlan` currently exposes no diagram renderer; its sealed
schematic intent remains inspectable while canonical renderer integration is
deferred.

The plan does not own artifact bindings, reductions, targets, objective meaning,
Gates, variables, optimizer settings, stage actions, receipts, or reporting.

### Explicit Port Loading Roles

`CircuitPlan.add_port(...)` requires an explicit `role` of either
`"terminated"` or `"nonloading_probe"`; there is no implicit default.
Terminated ports contribute their declared loading to targeted-Schur
optimization and Direct/HB response evaluation. Nonloading probes are excluded
from those loading paths but remain available to T1 evaluation and its existing
probe-shunt de-embedding.

The sealed plan exposes every port role. Stage requests and immutable receipts
identity-bind the applicable role map. Missing or invalid roles, identity
mismatches, and use of a port in a stage that does not permit its role fail
closed. Port roles select runtime loading behavior; they create no scientific
Gate or project-specific meaning.

## Objective And Artifact Declarations

`CircuitObjective.from_targets(...)` is the typed consumer-facing builder for
named cared outputs, target values, and weights. It compiles the mechanical
relative-residual expression. It does not own or reinterpret target values,
plan assembly, reductions, objective meaning, or Human Gates. Arbitrary Python
callbacks are not accepted.

`bind_artifact(...)` receives a path plus declared schema, units, and
provenance. The runtime derives the file hash. Consumers do not hand-author an
authoritative artifact hash or runtime-source hash.

## Staged Actions

The accepted workflow is ordered:

```text
optimize
-> refine_winner
-> evaluate_responses
-> fit_c11
-> evaluate_t1
-> build_report
```

This sequence expresses stage dependencies; it is not a new scientific Gate.
The public methods are:

```python
optimization = sim.optimize(action="execute")
refinement = sim.refine_winner(action="execute")
responses = sim.evaluate_responses(action="execute")
c11 = sim.fit_c11(action="execute")
t1 = sim.evaluate_t1(action="execute")
report = sim.build_report(action="execute")
```

Every method accepts exactly one semantic action mode:

| Mode | Contract |
| --- | --- |
| `execute` | Perform the complete named stage and seal its result. A stage that requires Julia starts exactly one Julia process for that action; it never spawns Julia per candidate or per frequency point. Python-owned fit/report stages start no Julia process. |
| `resolve` | Pure read-only verification and loading of the existing sealed stage. It starts no Julia process, performs no recomputation or mutation, and returns `NOT_EVALUABLE` when the stage is absent, stale, incomplete, corrupt, or identity-mismatched. |

There is no generic `run()` dispatcher and no compatibility path through the
superseded `evaluate` / `optimize` / `analyze` workflow. Stage dependencies
must resolve to complete `PASS` receipts before downstream execution.

### STABILIZED Anchored Direct Solve

`DirectSolveSpec` declares an independent `ReductionSpec`, ordered
`retained_labels`, one `root_label` that resolves to its zero-based index in
that sequence, and a positive finite `root_anchor_hz`.
`CircuitSim.direct_solve(spec, action="execute" | "resolve")` is an optional
operation, not part of the required six-stage report chain. It requires sealed
Plan and artifact identities plus either the configured externally selected
candidate or the sealed optimizer-winner/refinement identity. It creates no
Objective, Response, HB, C11, T1, optimization, refinement, or report
requirement.

The solve reuses JosephsonCircuits-assembled closed C/K/G, the current portless
compiled representation, complete-complement Schur reduction, and complex-root
validation. Terminated-port loading contributes to G; nonloading probes and
port P rows are absent. The anchor defines the initial condition for one
deterministic complex-Newton trajectory; the terminal root must satisfy the
full residual, machine-resolved simple-root, and passive-half-plane checks.
It is not a nearest-frequency or frequency-sorted selection rule.

`execute` computes and seals the operation once. `resolve` is pure read-only:
no Julia process and no recomputation. The receipt/result binds retained-label
order, resolved reduction and transform, selected label/index and anchor,
complex angular-root real and imaginary parts in rad/s, `frequency_hz`,
`linewidth_hz`, and numerical residual/simple-root evidence. Expected Schur or
root numerical non-evaluability seals `NOT_EVALUABLE` with its reason; malformed
labels/specification, invalid anchors, transform/reduction defects,
candidate/source or sealed-identity mismatches fail closed. There is no
scalar-LC shortcut, frequency-sort selection, stale-result reuse, compatibility
path, or fallback.

### ACCEPTED Standalone Direct Evaluation

`StandaloneDirectEvaluationSpec(readout_root_anchor_hz,
filter_root_anchor_hz, transfer_zero_anchor_hz)` declares three positive finite
numerical branch anchors.
`CircuitSim.evaluate_direct(spec, action="execute" | "resolve")` owns the
independent `evaluate_direct` stage. It uses the current sealed Plan, configured
`ReductionSpec`, variable and artifact bindings, and either the exact configured
external candidate or the sealed optimizer-winner/refinement identity.

The stage evaluates exactly:

- `readout_diagonal_root_hz`;
- `filter_diagonal_root_hz`;
- `transfer_cofactor_zero_hz`;
- `residue_normalized_midpoint_exchange_abs_real_hz`; and
- `diagonal_root_linewidth_sum_hz`.

The anchors select numerical branches, including the transfer-cofactor-zero
root branch. They are analysis controls, not targets, residuals, weights,
costs, Objectives, Gates, or scientific claims.

This operation requires no `CircuitObjective`, Response or HB declaration,
Direct S21 sweep, C11 fit, T1 evaluation, or report. It is not part of the
required report-stage chain. Existing objective-backed and targetless
five-output evaluation paths remain unchanged.

`execute` computes and seals the stage once. `resolve` is pure read-only: it
starts no Julia process and performs no recomputation. The request, receipt,
and result bind the `standalone_direct_evaluation` declaration, resolved
reduction, candidate source and identity, current Plan and artifact identities,
the five outputs, and their numerical evidence. Expected Schur or root
numerical failure seals `NOT_EVALUABLE` with its reason. Missing or malformed
declarations, stale Plan, reduction, artifact, candidate, or upstream-receipt
identities, mismatched current candidate selection, and tampered receipts fail
closed. A sealed `FAILED` receipt preserves its original failure metadata and
error. There is no fallback or compatibility path.

### ACCEPTED Optimization Progress Observer

An `execute` optimization may attach one process-local observer without
changing its final `ResolvedCircuitStage` return:

```python
def show_progress(progress: OptimizationProgress) -> None:
    print(f"Generation {progress.generation} / {progress.maximum_generations}")


optimization = sim.optimize(action="execute", on_progress=show_progress)
```

`OptimizationProgress` is immutable and contains exactly the 1-based count of
completed `generation`s and configured `maximum_generations`
(`OptimizerSpec.controls` `maxiter`). `maximum_generations` is a configured
ceiling, not a promise that optimization will reach it; existing stop
conditions may finish earlier. The callback runs on the Python caller thread
once after each completed CMA-ES population/generation and only after the
existing optimization ledger has been atomically written successfully; no
partial-generation event is emitted. `on_progress=None` preserves existing
execution behavior. `resolve` remains pure read-only and emits or replays no
callback, including when the same optional observer is supplied.

Progress is transient observability only. It is not part of the request,
ledger, fingerprint, receipt, artifact identity, result, objective, Gate, ETA,
candidate score, scientific semantics, claim, or acceptance evidence. If an
observer raises, the runtime warns once and disables further observer calls for
that invocation while the same Julia execution continues. The observer cannot
determine the stage result. The optimizer algorithm, seed, variables,
transforms, population, `maxiter`, `maxfevals`, objective, Gates, evaluation
order, ledger bytes and hash chain, stop behavior, receipts, results, and
one-Julia-process boundary remain unchanged.

Reusable components guarantee that named retainable coordinates survive from
the plan to matrix indices. JosephsonCircuits.jl parses the compiled closed
linear netlist and assembles full-system C/K/G. Workbench then performs the
declared complete-complement Schur reduction and extracts roots, transfer zero,
exchange, and linewidth quantities on the retained coordinates. Their physical
meaning remains with the consumer's accepted scientific authority.

`refine_winner` owns the declared N-to-2N cared-output comparison. Response
evaluation owns Direct and pump-off HB traces. Pump-off HB is a separate
response/cross-check backend, not a second solver inside the Direct targeted-
Schur optimization loop. `fit_c11` consumes the sealed HB
response, and `evaluate_t1` owns the HB-derived effective admittance and T1
surface. These are runtime mechanics; their consumer-supplied values and
scientific meaning remain outside Workbench ownership.

### Split Direct And HB Response Grids

`ResponseSpec.hb_frequency_hz` remains required and fail-closed. The
`CONVERGING` extension permits `direct_frequency_hz` to be an explicit Direct
S21 grid or explicit `None`. Existing callers that supply both grids retain
their current behavior.

`evaluate_responses(action="execute")` always performs the existing Direct
physical cared-output evaluation for the selected candidate. That evaluation
is distinct from the optional Direct S21 sweep. With a Direct grid, the stage
computes and seals `direct_response.csv`. With `direct_frequency_hz=None`, it
does not compute or seal that artifact. Pump-off HB remains required, runs on
`hb_frequency_hz`, and seals `hb_response.csv`. `fit_c11` remains HB-only and
seals `c11_fit.csv`; disabling Direct S21 does not change its input or failure
contract.

The sealed result and receipt bind the candidate source, Plan and artifact
identities, Direct physical `cared_outputs`, Direct S21 enabled-or-skipped
state, optional Direct grid and artifact, and required HB grid and artifact.
This applies equally to `optimizer_winner` and
`externally_selected_candidate`. It changes no optimizer, refinement,
candidate-selection, interpolation, or Direct-versus-HB comparison semantics.

### STABILIZED Targetless Direct Evaluation

An explicit candidate may request the five existing targeted-Schur Direct
physical quantities without declaring a `CircuitObjective`:

```python
responses = sim.evaluate_responses(
    action="execute",
    direct_evaluation=DirectEvaluationSpec(
        readout_root_anchor_hz=READOUT_ROOT_ANCHOR_HZ,
        filter_root_anchor_hz=FILTER_ROOT_ANCHOR_HZ,
        transfer_zero_anchor_hz=TRANSFER_ZERO_ANCHOR_HZ,
    ),
)
```

`DirectEvaluationSpec` carries only the three positive finite numerical branch
anchors. The sealed request expands it to exactly
`readout_diagonal_root_hz`, `filter_diagonal_root_hz`,
`transfer_cofactor_zero_hz`,
`residue_normalized_midpoint_exchange_abs_real_hz`, and
`diagonal_root_linewidth_sum_hz`, using the configured `ReductionSpec`. The
anchors select numerical branches; they are not targets, residuals, weights,
costs, Gates, or scientific claims.

This targetless path requires an exact externally selected candidate and does
not accept optimizer, refinement, or Gate declarations. It may execute the
existing Direct physical evaluation, optional Direct S21, required HB S21,
then the unchanged C11, T1, and report stages. Every request and receipt in the
chain, and the report manifest, binds the Direct declaration, candidate,
reduction, Plan, artifacts, and upstream receipts and records Objective and
Optimization as `NOT_REQUESTED`. The Response result carries the five Direct
outputs and its declaration. This path never fabricates an Objective or claims
optimization.

Existing objective-backed optimizer-winner and explicit-candidate calls remain
unchanged and do not accept a second Direct declaration. Targetless resolve is
read-only and requires the same method-local `DirectEvaluationSpec`, current
Plan, ReductionSpec, ResponseSpec, variables, artifacts, and explicit candidate;
absent, malformed, or stale bindings fail closed.

### CONVERGING Explicit-Candidate Evaluation

`CircuitSim.set_explicit_candidate(physical_parameters, provenance=...)` declares a
candidate for evaluation; it is not a stage, execution action, receipt,
optimizer, or internal solver-access path. The mapping uses the same requested
parameter-reference keys and physical values as
`winner_physical_parameters`. Its key set must match the current sealed Plan's
`VariableSpec` bindings exactly, with no missing, extra, foreign, or duplicate
reference. Values must be finite, dimensionally bound to those declared Plan
parameters, compatible with their transforms, and inside their declared
bounds. The runtime derives the canonical candidate identity; callers cannot
supply it.

The two sealed candidate sources are distinct:

```text
optimizer_winner
  -> optimize -> refine_winner -> evaluate_responses -> fit_c11 -> evaluate_t1 -> build_report

externally_selected_candidate
  -> declaration -> evaluate_responses -> fit_c11 -> evaluate_t1 -> build_report
```

The external path does not execute or claim `optimize` or `refine_winner` under
the current sealed Plan. Every downstream request and receipt binds the source
discriminator, physical mapping, declared provenance, derived candidate
identity, exact Plan and artifact bindings, and upstream receipt identities.
Candidate, Plan, artifact, or dependency mismatches fail closed. There is no
latest-result selection, fallback, compatibility path, parallel fitter, or
internal solver access. Reports display the explicit candidate and state that
optimization and N-to-2N refinement were not performed under the sealed Plan.
Existing stage and schema names remain unchanged.

## Identity, Receipts, And Failure

Python seals one request for each stage. The runtime automatically derives and
binds exact artifact, request, plan, Python Runtime, Julia Runner, Julia Core,
Julia executable, dependency-receipt, output-artifact, and output identities.

Each immutable stage receipt binds:

- request and plan identities;
- exact upstream receipt identities;
- input artifacts and runtime sources;
- produced artifacts and their hashes;
- completion or failure state; and
- explicit nonclaims.

A receipt seals only after the complete stage and declared artifact validation
succeed. Schema mismatch, missing or changed input, stale dependency, corrupt or
partial output, runtime identity mismatch, or failed execution remains closed;
no stale result, placeholder, permissive fallback, or fake success is returned.
An accepted scientific contract may separately define a typed
`NOT_EVALUABLE` result. Programming, schema, transport, and unexpected runtime
defects abort and seal failure where the request is valid enough to do so.

The existing public schema names remain:

| Schema | Owns |
| --- | --- |
| `circuit-workbench-plan.v1` | Libraries, component instances, values/units/roles, relations, ports, coordinate references, engineering graph, schematic intent, and canonical plan identity. |
| `circuit-workbench-run-request.v1` | Named stage, plan and input bindings, consumer declarations, dependencies, runtime identities, and request fingerprint. |
| `circuit-workbench-run-receipt.v1` | Request, plan, runtime, dependency and artifact identities; status/failure; result; and nonclaims. |

## Resolve And Reports

```python
result = resolve_circuit_result(RUN_DIR)
result.show_all_results()

campaign = resolve_circuit_campaign(EXPLICIT_RUN_DIRS)
campaign.show_all_results()
```

`resolve_circuit_result`, `resolve_circuit_campaign`, stage `resolve` actions,
and report-reading surfaces are pure Python and read-only. They never start
Julia, recompute, mutate, select a latest run, accept scientific meaning, or
fall back to incomplete evidence. A campaign preserves each explicitly supplied
run and its missing or failed state.

`build_report(action="execute")` is different: it seals the report stage and
its generated artifacts from already verified upstream receipts. Reading that
report through a resolver remains read-only. Generic result surfaces include
run trustworthiness, optimizer history and winner residuals, N-to-2N
comparison, Direct/HB/C11 responses, C11 fit parameters and residuals,
effective admittance/T1, timing, and provenance.

## Language And Privacy Boundary

Python is the routine client; Julia is the sole plan compiler and
circuit-compute authority. Consumer notebooks must not import `juliacall`, call
Julia Core directly, construct C/K/G, call Schur helpers, hand-write receipts,
or duplicate report calculations. The application service and async Julia
Runner remain a separate product execution surface.

This public contract describes only generic APIs and stage behavior. It does
not publish or accept a private component library, plan, variable, target,
objective, Gate, run identity, artifact, result, migration, compatibility shim,
or design-specific workflow.

## Semantic Status

- Scope: staged Circuit Runtime execution, resolution, receipt, and report
  contract described on this page.
- State: `STABILIZED`.
- State changed: 2026-08-22.
- Human acceptance: explicitly accepted the exact V1 packet for candidate
  `0b5ae925ea65b1006e3381c1220a45809c76b940`, tree
  `336d2a4e37ffa7fb829a748b188448afb1bec3b1`, and full-index diff SHA-256
  `771c821d7158d8f012647b08af99f6263705edf8f0f0de08980e80812fc9dfa7`.
- Supersedes: `ObjectiveSpec` and the generic `evaluate` / `analyze` workflow.
- Retained compatibility or migration: none.
- Stabilization evidence: Workbench `168132a843df1ed4eb5e2ffbd45f0d214c96fc83`
  freezes the six-stage execution and read-only resolution contract, receipt
  and artifact tamper rejection, dependency-chain validation, N-to-2N
  comparison, composite parameter binding, Direct matched-response internal-G
  propagation,
  partial report/campaign resolution, and removal of the superseded public
  surface. Runtime, Core, Runner, documentation integrity, and all four hosted
  PR checks passed at that revision.
- Test policy: `stabilization_tests_authorized`.
- Delivery status: `INTEGRATED` as Workbench
  `6b6d13156bd3d5074b7da90baed6af10399765e7`.
- Unresolved semantic decisions: none.

Optimization Progress Observer extension:

- State: `ACCEPTED`.
- Delivery status: `NOT_INTEGRATED`.
- Test policy: `stabilization_tests_authorized`.
- Human acceptance: explicitly accepted the exact candidate based on
  `d2f5c1936a3e0cee13fc9ec72d4f4b3b3037605d`, head
  `4996f8c1d9b92107c2839b7b48546fe928e0fe7e`, tree
  `23e2be4d6fff8694da683fb0f47c3f606b6118cc`, and full-index diff SHA-256
  `3cbb24684c6e78a16581ef30a77bd77008ff53830b25b715d28fcfd23dbfed3a`.
- Accepted scope: immutable `OptimizationProgress(generation, maximum_generations)`;
  optional process-local `sim.optimize(action="execute", on_progress=...)`; no
  observer effect on sealed requests, ledgers, fingerprints, receipts,
  artifacts, results, objectives, Gates, or scientific semantics.
- Unresolved semantic decisions: none.

Split Direct/HB response-grid extension:

- State: `STABILIZED`.
- Delivery status: Draft PR #43, `NOT_INTEGRATED`.
- Test policy: `stabilization_tests_authorized`.
- Human acceptance: explicitly accepted candidate
  `4d8ab2f573c6de5f39430e4261efd575593110fb`, tree
  `4d8d70dcced46c4187a216b41afdd07da6e45466`, and full-index diff SHA-256
  `b232309ab9d5ca3030d1cba439f01dc5c88c1f6bad9c8b3186c9edb7d59963c1`.
- Supersedes: the shared `ResponseSpec.frequency_hz` field.
- Retained compatibility or migration: none.
- Accepted scope: independent Direct and HB grids and artifacts, HB-only C11
  fitting, independent report frequency arrays, and fail-closed HB/C11 identity
  validation.
- Unresolved semantic decisions: none.

Optional Direct S21 extension:

- State: `CONVERGING`.
- Delivery status: `NOT_INTEGRATED`.
- Test policy: `no_test_writes`.
- Candidate scope: optional Direct S21 with always-on Direct physical
  cared-output evaluation, required HB response, HB-only C11 fitting, and
  explicit receipt binding of enabled or skipped Direct S21 state.
- Existing two-grid callers and optimizer semantics: unchanged.
- Human acceptance: not requested.
- Private or design-specific values: none.

Explicit port-role extension:

- State: `ACCEPTED`.
- Delivery status: Draft PR, `NOT_INTEGRATED`.
- Test policy: `stabilization_tests_authorized`.
- Accepted scope: required `terminated` or `nonloading_probe` roles; terminated
  loading in targeted-Schur optimization and Direct/HB response; nonloading
  probe exclusion from those paths with retained T1 probe-shunt de-embedding;
  sealed plan/request/receipt role binding; and fail-closed role validation.
- Implicit/default port role: none.
- Unresolved semantic decisions: none.

Explicit-candidate evaluation extension:

- State: `STABILIZED`.
- Delivery status: Workbench PR #46, `NOT_INTEGRATED`.
- Test policy: `stabilization_tests_authorized`.
- Human acceptance: on 2026-08-25 the Human explicitly accepted candidate
  `dd7ad23315e9a6fe2d2e62ffa112dac3d0df1832`, tree
  `50ac7817b7900dd15c00d123d470854869113dcf`.
- Accepted scope: a fixed candidate may execute Response → C11 → T1 → Report
  in the current sealed alternate-Plan run; receipts distinguish
  `externally_selected_candidate`; no optimization or refinement is claimed
  under that Plan.
- Scientific-result acceptance or SCNSim change: none.
- Retained compatibility or fallback: none.
- Unresolved semantic decisions: none.

`CircuitPlan` diagram surface:

- State: `STABILIZED`.
- Delivery status: `NOT_INTEGRATED`.
- Human acceptance: on 2026-08-23 the Human explicitly selected temporary
  absence of `CircuitPlan.show()` until canonical renderer integration is
  separately resumed.
- Supersedes: the runtime-private minimal preview and its Schemdraw dependency.
- Retained compatibility, fallback, or placeholder renderer: none.
- Test policy: `stabilization_tests_authorized`.
- Unresolved semantic decisions: none.

Anchored Direct Solve extension:

- State: `STABILIZED`.
- Delivery status: `INTEGRATED` as Workbench
  `d7da506a8cb729aea1096c662cd65800fd9087d4`.
- Test policy: `stabilization_tests_authorized`.
- Human acceptance: on 2026-09-01 the Human explicitly accepted candidate
  `516b6c6d52f0b9604e9376c4266d9c1c455ed450`, tree
  `33c0465a8b3cf343cc406936d5b3f8ad95cfd89c`, and full-index diff SHA-256
  `e816d28e6e9296e72697f8790db2d8b13a3a85ed06b3e6e2edd3fa8463c04b1a`
  after the D3 consumer preview.
- Accepted scope: optional independently sealed `DirectSolveSpec` operation
  for one anchored diagonal root of an explicit complete-complement reduction.
- Existing fixed staged pipeline: unchanged.
- Scientific-result acceptance: none.
- Private or design-specific values: none.
- Stabilization evidence: Workbench `31df7ee034e8713dfd302443469ed8a1db752813`
  freezes optimizer-winner and explicit-candidate execution, exact read-only
  Plan/spec/candidate binding, stale-selection rejection, result evidence,
  numerical `NOT_EVALUABLE`, and exclusion from the fixed report pipeline.
  Python Runtime, Julia Runner, and Julia Core suites passed.
- Unresolved semantic decisions: none.

Targetless Direct evaluation extension:

- State: `STABILIZED`.
- Delivery status: `INTEGRATED` as Workbench
  `0bc1c19c9d3505a5eaff6e4ec899bbc3bbb23726`.
- Test policy: `stabilization_tests_authorized`.
- Accepted scope: an externally selected candidate may execute the existing
  targeted-Schur Direct physical evaluation and Response → C11 → T1 → Report
  chain without `CircuitObjective`; Objective and Optimization are sealed as
  `NOT_REQUESTED`.
- Existing objective-backed behavior: unchanged.
- Human acceptance: on 2026-09-01 the Human explicitly accepted candidate
  `436bc36e631907956d409a8f90cfcc032f255de0`, tree
  `5829295e311b6b5f498baed9419e9937bda3360c`, and full-index diff SHA-256
  `4ca9459285e4d35992ea888d4b73c92fb6144e8fcf1bbcec8a4ae7353a1c10f3`
  after the real D3 consumer preview.
- Scientific-result acceptance: none.
- Private or design-specific values: none.
- Stabilization evidence: the public-safe Runtime regression freezes the exact
  explicit candidate and Direct declaration, absent or stale binding
  rejection, disabled Direct S21, required HB, the C11 → T1 → Report chain,
  `NOT_REQUESTED` evidence, receipt tamper rejection, and pure read-only
  resolution. The complete Python Runtime suite passed with 12 tests.
- Unresolved semantic decisions: none.

Standalone Direct evaluation extension:

- State: `ACCEPTED`.
- Delivery status: Workbench PR #50, `NOT_INTEGRATED`; protected `develop`
  remains Workbench `20089deb02a2b319e1e43385672d76ed9ba9630c` until
  Integration completes this accepted extension.
- Test policy: `stabilization_tests_authorized`.
- Human acceptance: on 2026-09-03 the Human explicitly accepted the
  transfer-zero extension at source head
  `1e3b9851ed2aa001c3fac31a65bed03a080d5918`, tree
  `5904c82d02f0bd76ab64287d94a56b500350d7b1`, with canonical full-index
  diff SHA-256
  `71d9f64c242bb739c1a73640bb7d0b62f86cf7e47f84ca8b85cbf672fd69f645`.
- Accepted scope: independent `evaluate_direct` execution and pure read-only
  resolution for exactly five targeted-Schur R/P quantities, including
  `transfer_cofactor_zero_hz`, using either the exact external candidate or
  sealed optimizer-winner/refinement identity. The Objective, Response/HB,
  S21, C11, T1, and report surfaces are excluded.
- Existing objective-backed and targetless five-output paths: unchanged.
- Scientific-result acceptance: none.
- Private or design-specific values: none.
- Retained compatibility or fallback: none.
- Stabilization evidence: pending completion of exact contract alignment and
  relevant validation in Workbench PR #50.
- Unresolved semantic decisions: none.

## Related

- [Notebook Roles](notebook-roles.md)
- [Tech Stack](../guardrails/project-basics/tech-stack.mdx)
- [Source of Truth Order](../guardrails/project-basics/source-of-truth-order.mdx)
- [Quantum Model Boundary](quantum-model-boundary.md)
