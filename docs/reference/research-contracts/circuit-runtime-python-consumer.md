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
last_updated: 2026-08-23
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
    GateSpec,
    OptimizationProgress,
    OptimizerSpec,
    ReductionSpec,
    ResponseSpec,
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
callback. `plan.show()` validates and renders without Julia or a numerical
evaluability claim.

The plan does not own artifact bindings, reductions, targets, objective meaning,
Gates, variables, optimizer settings, stage actions, receipts, or reporting.

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

## Related

- [Notebook Roles](notebook-roles.md)
- [Tech Stack](../guardrails/project-basics/tech-stack.mdx)
- [Source of Truth Order](../guardrails/project-basics/source-of-truth-order.mdx)
- [Quantum Model Boundary](quantum-model-boundary.md)
