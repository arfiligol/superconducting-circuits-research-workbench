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
version: v1.2.0
last_updated: 2026-05-28
updated_by: codex
---

# Authoring Model

Julia Core authoring starts from reusable components and plan-level relations. Users write component and coupling intent; they do not author simulator rows as the primary workflow.

The compiler lowers one complete Circuit Plan into the JosephsonCircuits.jl target. Component composition stays in the plan and is flattened only during global compilation.

## Docs-First Rule

The Julia Core Authoring reference is the source of truth for the next implementation. If implementation names, exports, or builder helpers conflict with these pages, update the implementation to match this authoring model.

Do not preserve outdated APIs as fallback or compatibility layers when they obscure the Circuit Plan, endpoint, compiler, or compiled-circuit contracts.

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

Users build a `CircuitPlan`, add components from a selected Component Library, connect endpoints, add couplings, validate the plan, and then call the compiler.

The following example assumes a component library provides `GroundedLCResonatorComponent` and `QuarterWaveResonatorComponent` builders:

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
    to = line_tap(qwr; line = :main, at_m = 1.2mm),
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

These examples describe component-library definitions that use the Julia Core authoring contract.

## Component Libraries

The authoring model is designed so users, labs, and projects can define their own reusable components.

Julia Core defines the framework:

- how components expose endpoints;
- how components are inserted into a Circuit Plan;
- how relations and couplings target endpoints;
- how validation and compiler lowering are organized;
- how compiled circuits preserve maps and provenance.

Julia Core does not need to own every concrete component family.

Concrete families such as `GroundedLCResonatorComponent`, `FloatingLCResonatorComponent`, `QuarterWaveResonatorComponent`, and `CPWFluxLineComponent` should be treated as examples of component-library definitions, not as a closed Julia Core catalog.

## Transitional Names

`CircuitDraft` is a transitional implementation detail, not the architecture contract. The target concept is `CircuitPlan`.

If code still exposes `CircuitDraft`, implementation work may rename, remove, or replace it while aligning to this reference. The same rule applies to old direct-netlist helpers such as `finalize_to_josephson_netlist`; the target compiler concept is `compile_to_josephson(plan)`.

## Boundaries

| Rule | Meaning |
| --- | --- |
| Components are Plan-level objects | They can expose public pins, own private nodes, contain elements, or contain subcomponents. |
| Relations are Plan-level intents | `connect!`, `couple_capacitive!`, `couple_window!`, and related calls are not immediate netlist rows. |
| Compiler owns lowering | JosephsonCircuits.jl-specific rows are emitted only after plan validation and endpoint resolution. |
| Pluto and Runner share the path | Pluto should not require a special compute path; Runner execution should call the same Core authoring and compiler logic. |
| Framework boundaries stay outside Core | Julia Core must not depend on FastAPI, Next.js, Electron, or Backend task state. |
