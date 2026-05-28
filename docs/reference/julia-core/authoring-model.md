---
aliases:
  - Julia Core Authoring Model
  - Circuit Authoring Model
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Source-of-truth authoring model for reusable Julia Core circuit components, plans, and compiler lowering.
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Authoring Model

Julia Core authoring starts from reusable components and plan-level relations. Users write component and coupling intent; they do not author simulator rows as the primary workflow.

The compiler lowers one complete Circuit Plan into the JosephsonCircuits.jl target. Component composition stays in the plan and is flattened only during global compilation.

## Contract

```text
Reusable Circuit Components
        |
        v
Circuit Plan
        |
        v
Plan-level relations / couplings / transforms
        |
        v
Compiler
        |
        v
JosephsonCircuits.jl target netlist
```

The correct unit of reuse is the Plan-level component, not a precompiled netlist fragment.

!!! warning "Do not append compiled component fragments"
    Do not describe or implement a workflow where each component is compiled into a JosephsonCircuits.jl netlist and those netlists are appended together. The complete plan must be compiled once so endpoints, private nodes, line taps, spans, couplings, and provenance can be resolved consistently.

## Happy Path

```mermaid
flowchart LR
    Component["Component"] --> Plan["Circuit Plan"]
    Plan --> Compiler["Compiler"]
    Compiler --> Netlist["JosephsonCircuits.jl Netlist"]
```

Users build a `CircuitPlan`, add components, connect endpoints, add couplings, validate the plan, and then call the compiler.

```julia
plan = CircuitPlan(id = "example")

lc = add_grounded_lc_resonator_component!(
    plan;
    id = "lc",
    capacitance = Capacitor(80.0fF),
    inductive_element = LinearInductor(8.0nH),
)

qwr = add_quarter_wave_resonator_component!(plan; id = "qwr", line_spec = qwr_spec)

couple_capacitive!(
    plan;
    id = "lc_to_qwr",
    from = pin(lc, :signal),
    to = line_tap(qwr; at_m = 1.2mm),
    capacitance = 3.0fF,
)

compiled = compile_to_josephson(plan)
```

## Component Hierarchy

```mermaid
flowchart LR
    Primitive["Primitive Element"] --> Composite["Composite Component"]
    Composite --> Plan["Circuit Plan"]
    Plan --> Compiler["Compiler"]
```

Primitive elements and composite components are both Plan-level objects. A composite may contain subcomponents, primitive elements, public pins, private internal nodes, local parameters, and provenance.

The hierarchy remains inspectable until compilation:

```text
GroundedLCResonator
    = Capacitor(signal, ground) + InductiveElement(signal, ground)

SQUID
    = JosephsonJunction + JosephsonJunction + optional loop inductance + flux parameter
```

## Current Implementation Name

`CircuitDraft` is the current implementation of the Circuit Plan authoring model.

Docs should use `Circuit Plan` for the architecture concept and may mention `CircuitDraft` only as the current implementation name. This docs task does not require a code rename.

## Boundaries

| Rule | Meaning |
| --- | --- |
| Components are Plan-level objects | They can expose public pins, own private nodes, contain elements, or contain subcomponents. |
| Relations are Plan-level intents | `connect!`, `couple_capacitive!`, `couple_window!`, and related calls are not immediate netlist rows. |
| Compiler owns lowering | JosephsonCircuits.jl-specific rows are emitted only after plan validation and endpoint resolution. |
| Pluto and Worker share the path | Pluto should not require a special compute path; Worker execution should call the same Core authoring and compiler logic. |
| Framework boundaries stay outside Core | Julia Core must not depend on FastAPI, Next.js, Electron, or Backend task state. |
