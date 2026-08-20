---
aliases:
 - Circuit Workbench Runtime
 - Python circuit consumer
tags:
 - diataxis/reference
 - audience/team
 - sot/true
 - topic/research-contracts
status: accepted
owner: docs-team
audience: team
scope: Accepted public Circuit Workbench runtime and Python-consumer boundary.
version: v1.0.1
last_updated: 2026-08-21
updated_by: codex
title: Circuit Runtime / Python Consumer
description: Accepted V1 contract for visible Python circuit plans, Julia action execution, sealed evidence, and pure-Python analysis.
sidebar:
 label: Circuit Runtime / Python Consumer
 order: 45
---

# Circuit Runtime / Python Consumer

This page records the Human-accepted V1 consumer contract. Delivery is separate:
the runtime implementation and generated API reference remain owned by the
Workbench implementation package and must bind this contract before integration.

Contract artifact SHA-256:
`e1c2fc83c91a2fff94c4fd59f8bf919e69c2e3bf7ef8a2489874068f971e52ef`.
The accepted source baseline is Workbench
`f78b04f35f974c0f4fdaf4e60895df2c289c04f6`.

## Bound Implementation Candidate

Delivery remains `NOT_INTEGRATED`. The current implementation binding is
[Workbench PR #32](https://github.com/arfiligol/superconducting-circuits-research-workbench/pull/32):

| Identity | SHA |
| --- | --- |
| Base | `f78b04f35f974c0f4fdaf4e60895df2c289c04f6` |
| Head | `182a1f1781b69a14cdc84fbeac07e98cd4eb59ae` |
| Tree | `32d9e332bbcca3d0ddba34f6ed8147545aa87558` |
| Base-to-head full-index binary diff SHA-256 | `5754aa010ecfbfa8d08cb889fd20222591bbeafb5c1e854a99c7ecf0e309b315` |

This binding records delivery provenance only. It does not change the accepted
public semantics below and does not claim integration, release, or deployment.

## Ownership Boundary

| Owner | Owns |
| --- | --- |
| Workbench runtime | Public package and schemas; element/relation semantics; public component catalog; whole-plan compiler; Direct C/K/G; coordinate transforms; complete-complement Schur reduction; HB; optimizer execution; fingerprints and receipts. |
| Consumer | Notebook source; visible `CircuitPlan`; consumer libraries; artifact bindings; reduction and cared outputs; objective; exact Human-authorized Gates; optimizer specification; run evidence. |
| Root SCQ Design Kit / Human | Reusable scientific meaning, Design Targets, Gate authority, acceptance, and decision history. |
| Layout and solver owners | Layout, geometry, materials, and solver artifacts consumed through sealed bindings. Workbench does not execute those solvers. |

Public examples remain with their public consumers. Private plans, libraries,
inputs, and results remain with their private owner.

## Public Surface

The distribution is `superconducting-circuits-runtime`; its import name is
`superconducting_circuits_runtime`.

```python
from superconducting_circuits_runtime import (
    CircuitLibrary,
    CircuitPlan,
    CircuitSim,
    GateSpec,
    ObjectiveSpec,
    OptimizerSpec,
    ReductionSpec,
    VariableSpec,
    circuit_component,
)
```

Catalog components come from `superconducting_circuits_runtime.catalog`.
Python analysis remains a separate package and is not a circuit-compute
implementation.

### Visible plan

`CircuitPlan` is the sole complete-plan container. It owns topology, parameters,
connections, ports, and inspectable engineering and schematic intent. Every
placed object is an instance of a registered component type; a plan is not a
dictionary, compiled netlist fragment, or design-specific subclass.

A `@circuit_component` factory may compose registered types, but it must seal a
component/relationship graph before Julia starts. It cannot become a Python
callback during compilation or candidate evaluation. `plan.show()` validates
and renders through the schematic-export/Schemdraw path without starting Julia
or claiming numerical evaluability.

The plan does **not** own artifact bindings, retained/eliminated coordinates,
cared outputs, objective, Gates, variables, or optimizer settings. Those remain
explicit consumer declarations on `CircuitSim`.

### Explicit stages and actions

```python
sim = CircuitSim(run_root=RUN_ROOT, run_id=RUN_ID)
sim.register_library(library)
sim.set_plan(plan)
sim.bind_artifact("q2d", q2d_artifact)
sim.set_reduction(reduction)
sim.set_objective(objective)
sim.set_gates(gates)
sim.set_variables(variables)
sim.set_optimizer(optimizer)

result = sim.evaluate(backend="direct")  # or "hb"
search = sim.optimize()
report = sim.analyze()
```

There is no generic `run()` dispatcher and no notebook-facing Schur helper.
The notebook keeps `WORKFLOW_ACTION = "evaluate" | "optimize" | "analyze"`
visible and calls the matching explicit method.

| Action | Execution | Result |
| --- | --- | --- |
| `evaluate(backend="direct" | "hb")` | One Julia process for the complete evaluation. Julia compiles the whole plan, binds artifacts, transforms, reduces, evaluates, and seals evidence. | Typed Python handle plus run receipt. |
| `optimize()` | One Julia process for the complete search. Candidate and frequency-point work never calls back into Python. | Result, deterministic progress ledger, winner identity, and run receipt. |
| `analyze()` | Pure Python. It verifies the receipt, fingerprint, and artifact hashes and loads existing evidence. | Python result/report objects; optional consumer-owned presentation. |

`analyze()` never starts Julia and never silently recomputes. Missing,
incomplete, stale, or identity-mismatched evidence is an error.

## Declarative Scientific Inputs

- `ReductionSpec` uses coordinate references from registered instances, ordered
  transforms, an explicit retained set, and
  `eliminated="complete_complement"`. Julia constructs and executes the
  reduction.
- `ObjectiveSpec` is a restricted serializable expression graph over named
  cared outputs. Arbitrary Python callbacks are forbidden.
- `GateSpec` is separate from objective cost. Only an active Gate carrying an
  exact Human authority reference may reject, stop, or promote. Inactive
  proposals are diagnostics only.
- `VariableSpec` binds physical parameter references and transforms.
- `OptimizerSpec` records algorithm, seed, resources, and Human-authorized
  search controls. Resources may affect throughput, not deterministic candidate
  order, cost ledger, tie breaking, or result identity for a fixed request.

## Language and Evidence Boundary

Python is the routine client; Julia is the sole compiler and circuit-compute
authority. Python seals one action request and fingerprint. Julia writes into a
temporary action directory and atomically seals the receipt only after declared
artifacts exist and their hashes match.

Small control documents use canonical JSON. Large arrays use sealed files or
Zarr references and do not travel through HTTP JSON. V1 has three top-level
schemas:

| Schema | Owns |
| --- | --- |
| `circuit-workbench-plan.v1` | Libraries, component instances, values/units/roles, relations, ports, coordinate references, engineering graph, schematic intent, and canonical plan hash. |
| `circuit-workbench-run-request.v1` | Action, plan identity, bindings, reduction, cared outputs, objective, Gates, variables, optimizer/resources, runtime source pin, and fingerprint. |
| `circuit-workbench-run-receipt.v1` | Request/fingerprint identity, runtime identities, source/output hashes, lifecycle and data classification, status/failure, progress identity, result references, and nonclaims. |

Consumer notebooks must not import `juliacall`, invoke Julia Core directly,
construct C/K/G, call Schur helpers, or require the desktop application or its
managed numeric store. The existing Julia-to-Python Analysis Bridge remains
one-way analysis infrastructure; it is not inverted into this runtime.

## Fail-Closed Contract

The runtime fails when a component, pin, coordinate, relation, parameter, unit,
library identity, artifact binding, or declarative reference is missing or
ambiguous; when a plan cannot be sealed; when evidence is absent, stale,
malformed, incomplete, or hash-mismatched; when an active Gate lacks exact Human
authority; or when compilation, evaluation, optimization, resume, or receipt
sealing fails.

A scientific contract may define a typed `NOT_EVALUABLE` candidate result.
Programming, schema, transport, and unexpected runtime defects instead abort.
No placeholder value, stale result, permissive fallback, or fake success is
allowed.

## Supersession and Nonclaims

This contract supersedes general statements that restrict Python notebooks to
exported-result inspection or require the application service/Julia Runner for
routine circuit evaluation. The application remains a separate persisted async
surface with its own service, runner, authorization, storage, and publication
contracts.

This package does not migrate D3, add a D3 compatibility shim, accept a private
component/objective/Gate/result, change a Design Target, or authorize
publication. Existing D3 bytes remain unchanged and replayable until a separate
owner package proves equivalence and receives an explicit pin-switch decision.

## Related

- [Notebook Roles](notebook-roles.md)
- [Tech Stack](../guardrails/project-basics/tech-stack.mdx)
- [Source of Truth Order](../guardrails/project-basics/source-of-truth-order.mdx)
- [Quantum Model Boundary](quantum-model-boundary.md)
