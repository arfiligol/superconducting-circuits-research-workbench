---
aliases:
  - Reusable Circuit Components
  - Components and Composition
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Plan-level reusable circuit components, primitive elements, composition, public pins, private nodes, and namespace rules.
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Components and Composition

A reusable circuit component is a Plan-level object. It can expose public pins, own private internal nodes, contain primitive elements, contain subcomponents, and define local parameters.

Component composition is Plan-level hierarchy. It is not compiled-netlist-level concatenation.

## Component Families

| Family | Examples |
| --- | --- |
| Primitive Elements | `Capacitor`, `LinearInductor`, `JosephsonJunction` |
| Inductive Elements | `LinearInductor`, `SingleJunction`, `SQUID` |
| Lumped Resonator Components | `GroundedLCResonatorComponent`, `FloatingLCResonatorComponent` |
| Distributed Components | `ReadoutLineComponent`, `CPWFluxLineComponent`, `QuarterWaveResonatorComponent`, `HalfWavePurcellFilterComponent` |

Primitive elements may be used directly or inside composite components. Composite components may contain smaller components and primitive elements.

## Composition Rules

| Rule | Contract |
| --- | --- |
| Public pins | Components expose stable user-facing attachment names such as `:signal`, `:plus`, `:minus`, or `:feed`. |
| Private internal nodes | Components may own internal implementation nodes; users should not need those names. |
| Subcomponents | Composite components may include smaller components and primitive elements. |
| Local parameters | Components may carry local values, sweep knobs, and provenance. |
| Line references | Distributed components with multiple internal lines must expose named line references such as `line_ref(component, :main)`. |
| Namespacing | The compiler namespaces private nodes and subcomponent internals when it expands hierarchy. |
| Flattening | Composite components are flattened by the global compiler after endpoint resolution and validation. |

!!! warning "Reusable units"
    Compiled netlist fragments should not be used as reusable components. Reuse the Plan-level component and let the global compiler lower the complete Circuit Plan.

## Composite Examples

```text
SQUID
    = JosephsonJunction + JosephsonJunction + optional loop inductance + flux parameter

GroundedLCResonator
    = Capacitor(signal, ground) + InductiveElement(signal, ground)

FloatingLCResonator
    = Capacitor(plus, minus) + InductiveElement(plus, minus)
```

The same high-level resonator component can accept replaceable inductive elements.

## Grounded LC With Replaceable Inductive Elements

```julia
lc1 = add_grounded_lc_resonator_component!(
    plan;
    id = "lc1",
    capacitance = Capacitor(80.0fF),
    inductive_element = LinearInductor(8.0nH),
)

lc2 = add_grounded_lc_resonator_component!(
    plan;
    id = "lc2",
    capacitance = Capacitor(75.0fF),
    inductive_element = SingleJunction(Ic = 25.0nA, Cj = 2.0fF),
)
```

The user changes the inductive element without changing the resonator's public attachment model.

## Grounded LC With SQUID

```julia
flux_line = add_cpw_flux_line_component!(plan; id = "flux", line_spec = flux_line_spec)

lc = add_grounded_lc_resonator_component!(
    plan;
    id = "squid_lc",
    capacitance = Capacitor(80.0fF),
    inductive_element = SQUID(
        junction_a = JosephsonJunction(Ic = 25.0nA, Cj = 2.0fF),
        junction_b = JosephsonJunction(Ic = 25.0nA, Cj = 2.0fF),
        external_flux = Parameter(:phi_ext),
    ),
)
```

The SQUID remains a component hierarchy in the plan. Its loop endpoint can be targeted by an inductive relation in the same Circuit Plan.

Distributed components may also expose line references for taps and spans:

```julia
main_line = line_ref(flux_line, :main)
tap = line_tap(main_line; at_m = 2.0mm)
```

The component-level shorthand `line_tap(flux_line; at_m = 2.0mm)` is valid only when the component has one unambiguous default line. Multi-line components must use `line_ref` or pass `line = :main`.

## Floating LC With Replaceable Inductive Element

```julia
flc = add_floating_lc_resonator_component!(
    plan;
    id = "flc",
    capacitance = Capacitor(80.0fF),
    inductive_element = SQUID(...),
)
```

Floating components expose two public attachment points, commonly `:plus` and `:minus`.

## Namespace Ownership

User-facing code should use public pins and endpoints:

```julia
pin(lc, :signal)
pin(flc, :plus)
pin(flc, :minus)
```

It should not require internal node names from the component implementation. Private names are compiler-managed and may change when the component hierarchy changes.
