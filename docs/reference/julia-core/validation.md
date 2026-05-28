---
aliases:
  - Julia Core Validation
  - Circuit Plan Validation
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Validation layers for authoring, compilation, and physics sanity in the Julia Core Circuit Plan pipeline.
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Validation

Validation is layered so callers can catch simple authoring mistakes early, compile-time topology issues before target emission, and physics sanity risks before expensive simulation.

Validation does not replace the compiler. It protects each stage of the Core pipeline.

## Layers

| Layer | Runs against | Main question |
| --- | --- | --- |
| Authoring validation | Circuit Plan while users build it | Is the plan structurally well-formed? |
| Compile validation | complete Circuit Plan before or during lowering | Can the compiler resolve and lower this plan consistently? |
| Physics sanity validation | plan and compiled output | Are the values and discretization physically plausible enough to simulate? |

## Authoring Validation

Authoring validation catches local plan mistakes:

- duplicate component IDs;
- invalid pins;
- invalid element values;
- invalid span length.

These errors should be clear in Pluto and deterministic in Runner builds.

## Compile Validation

Compile validation catches global lowering problems:

- unresolved endpoints;
- overlapping line transformations;
- missing coupled-window endpoints;
- invalid tap location;
- ambiguous line taps or spans on components with more than one possible line.

This layer has access to the complete plan, so it can reason across components, aliases, taps, spans, and coupling windows.

## Physics Sanity Validation

Physics sanity validation catches values that may compile but are likely wrong:

- negative capacitance;
- invalid mutual coupling;
- suspicious discretization;
- missing nonlinear parameters.

These checks may produce errors or warnings depending on severity and caller policy.

## Caller Behavior

| Caller | Expected validation behavior |
| --- | --- |
| Pluto | surface validation messages near the authoring cell and keep inspection interactive |
| Julia Runner | fail deterministic task builds clearly when required validation fails |
| Compiler | include recoverable warnings in `JosephsonCompiledCircuit.warnings` |

Validation output should use endpoint and component IDs from the Circuit Plan, not private target netlist row details, whenever possible.
