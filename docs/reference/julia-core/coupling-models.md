---
aliases:
  - Julia Core Coupling Models
  - Coupling Model Layer
  - MTL Coupled Window
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Julia Core coupling taxonomy for point capacitive coupling, point mutual inductive coupling, distributed MTL coupled windows, and physical line generators.
version: v1.6.0
last_updated: 2026-05-30
updated_by: codex
---

# Coupling Models

Julia Core treats coupling as a domain model, not as ad hoc notebook code. A single capacitor can model point capacitive coupling, but it must not stand in for a finite-length CPW / MTL coupled window.

The active contract has three levels.

## Level 1: Primitive Coupling Relation

Primitive relations are the lowest authoring layer that still carries engineering meaning.

### Point Capacitive Coupling

```julia
couple_capacitive!(
    plan;
    id="readout_filter_cin",
    from=input_node,
    to=filter_node,
    capacitance=2.0e-15,
)
```

This means one capacitor `Cc` between two circuit nodes. It is a point coupling relation. It does not model a finite-length CPW or MTL coupling window.

Use it for localized capacitive ports, lumped pads, small intentional capacitors, or first-order filter/resonator examples where the notebook clearly says the model is point-coupled.

### Point Mutual Inductive Coupling

```julia
couple_inductive!(
    plan;
    id="m12",
    inductor_a=line_a.series_inductors[2],
    inductor_b=line_b.series_inductors[2],
    mutual_inductance=3.0e-12,
)
```

or:

```julia
couple_inductive!(
    plan;
    id="k12",
    inductor_a=line_a.series_inductors[2],
    inductor_b=line_b.series_inductors[2],
    coupling_coefficient=0.08,
)
```

Branch mutual coupling validates:

```text
abs(M) < sqrt(L1 * L2)
-1 < k < 1
M = k * sqrt(L1 * L2)
```

Compiler lowering emits a JosephsonCircuits `K_...` row between the two generated inductor rows.

!!! warning "Endpoint inductive coupling"
    The older endpoint-style `couple_inductive!(from=..., to=...)` still records flux / loop intent, but it is not the MTL branch-coupling path. Use `inductor_a` / `inductor_b` for lowerable mutual inductance between ladder sections.

## Level 2: Structured Coupling Helper

### MTL / CPW Coupled Window

```julia
window = couple_transmission_window!(
    plan;
    id="readout_qwr_mtl_window",
    line1=readout_line,
    line2=qwr,
    start1=2.25e-3,
    start2=0.0,
    length=1.5e-3,
    model=MTLCoupledWindowSpec(...),
)
```

An MTL coupled window is a finite distributed region between two transmission-line ladders. It is not a single `Cc`. The sectioned representation is driven by the `RLGCSpec` self values on each line plus the distributed coupling values in the coupled-window model.

For each coupled section, Julia Core keeps the original line sections and adds:

```text
Line 1:
  series L1
  shunt C1g

Line 2:
  series L2
  shunt C2g

Between lines:
  C12 between corresponding section nodes
  M12 / K between corresponding section inductors
```

Coupled-window invariants are strict:

| Constraint | Contract |
| --- | --- |
| Sections | every coupled segment must have explicit section parameters |
| Boundaries | `start1`, `start2`, and `length` must resolve to generated section boundaries |
| Section geometry | corresponding coupled sections must have matching physical length |
| Self values | line self values come from each line's `RLGCSpec` |
| Coupling values | `c12_per_m_f` and `lm_per_m_h` scale by the actual coupled-section length |

No silent snapping or interpolation is allowed. Builders create semantic section boundaries at physical window starts and ends so the requested physical window is preserved.

## EngineeringGraph Relation

`couple_transmission_window!` records primitive C12 and M12 relations and a semantic window relation:

```text
relation_type = :coupled_window
from = (line = "readout_line", sections = i:j)
to = (line = "qwr", sections = k:l)
through = MTLCoupledWindowSpec(...)
parameters = start distances, length, section count, per-unit coupling values
```

This lets notebooks show statements such as:

```text
readout_line sections 4:5 couple to qwr sections 1:2
```

without reverse-engineering the compiled netlist.

## Level 3: Physical Component / Model Generator

Physical generators convert physical parameters into primitive relations.

| Generator | Output |
| --- | --- |
| `build_lc_ladder_line!` | `TransmissionLineLadder` from `RLGCSpec` with ordered nodes, series inductors, shunt capacitors, and terminations |
| Quarter-wave resonator | ladder with grounded/coupled head and open tail |
| Half-wave resonator | usually open-open or capacitively coupled at both ends |
| Readout line + QWR | readout ladder, QWR ladder, and `couple_transmission_window!` |
| Even/odd coupled-line specification | converted into per-unit mutual capacitance and inductance before ladder generation |

Notebooks may call these APIs and inspect their output. They should not hand-code CPW ladder or MTL coupled-window conventions that belong in Core.
