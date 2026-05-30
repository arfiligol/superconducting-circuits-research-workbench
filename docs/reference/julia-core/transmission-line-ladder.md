---
aliases:
  - Transmission Line Ladder
  - CPW LC Ladder
  - Julia Core RLGCSpec
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Julia Core transmission-line ladder conventions for CPW / RLGC modeling, head/tail orientation, section indexing, and open/short terminations.
version: v1.6.0
last_updated: 2026-05-30
updated_by: codex
---

# Transmission Line Ladder

`RLGCSpec` and `build_lc_ladder_line!` are the user-facing Julia Core contract for CPW / transmission-line LC ladders.

They define orientation, sectioning, generated primitive relations, and boundary conditions so Pluto notebooks can teach the physics without reimplementing ladder conventions.

## Specification

```julia
spec = RLGCSpec(
    length_m=6.0e-3,
    section_length_m=0.75e-3,
    l_per_m_h=4.2e-7,
    c_per_m_f=1.7e-10,
    r_per_m_ohm=0.0,
    g_per_m_s=0.0,
)
```

Required fields:

| Field | Meaning |
| --- | --- |
| `length_m` | physical line length |
| `section_length_m` or `n_sections` | discretization reference / section-count contract |
| `l_per_m_h` | series inductance per meter |
| `c_per_m_f` | shunt capacitance to ground per meter |
| `r_per_m_ohm` | optional series resistance per meter |
| `g_per_m_s` | optional shunt conductance per meter |

`length_m` is exact. When `section_length_m` is provided, Julia Core treats it as a reference or maximum section length:

```julia
n_sections = ceil(Int, length_m / section_length_m)
actual_dx = length_m / n_sections
```

The generated ladder preserves the physical length and scales every section value from `actual_dx`. The requested `section_length_m` never moves the physical head, tail, or coupling-window boundary.

## Head / Tail Convention

Every generated line has:

```text
head endpoint
tail endpoint
ordered nodes from head to tail
section index starting at 1 from the head
```

For `N` sections, the ladder has `N + 1` ordered nodes:

```text
nodes[1]     = head
nodes[2]     = first internal/tail-side node
...
nodes[N + 1] = tail
```

Section `i` spans:

```text
nodes[i] -> nodes[i + 1]
```

This orientation is mandatory because coupled windows are specified by distance from each line head.

## Section Values

For an actual section length `dx`:

```julia
L_section = l_per_m_h * dx
C_section = c_per_m_f * dx
R_section = r_per_m_ohm * dx
G_section = g_per_m_s * dx
```

`build_lc_ladder_line!` emits a series inductor for every section and a shunt capacitor at each section tail node unless that node is a grounded terminal.

When `r_per_m_ohm > 0`, each section includes a series resistor before its series inductor. When `g_per_m_s > 0`, each shunt conductance is represented by a resistor `1 / G_section` to ground.

## Builder

```julia
line = build_lc_ladder_line!(
    plan;
    id="readout_line",
    head=input_node,
    tail=output_node,
    spec=spec,
    head_termination=:external,
    tail_termination=:open,
)
```

The returned `TransmissionLineLadder` exposes:

```julia
line.nodes
line.series_inductors
line.shunt_capacitors
line.head
line.tail
line.section_lengths_m
line.section_boundaries_m
```

Use these helpers for generated-boundary lookup:

```julia
node_at_distance(line, 1.5e-3)
section_index_at_distance(line, 1.5e-3)
section_range_from_window(line, 2.25e-3, 1.5e-3)
```

All distances are measured from the head. A distance must resolve to a generated section boundary. CPW and coupled-window builders therefore create section boundaries at physical endpoints and semantic window boundaries before generating primitive relations.

## Terminations

| Termination | Meaning |
| --- | --- |
| `:external` | no ground connection; usually connected to a port or another network |
| `:open` | terminal node is not connected to ground |
| `:short` / `:grounded` / `:ground` | terminal node is connected to ground |

An open end means:

```text
The terminal node is not connected to ground.
```

A short / grounded end means:

```text
The terminal node is connected to ground.
```

Julia Core skips the final shunt capacitor at a grounded tail so the compiled netlist does not emit a capacitor from ground to ground.

## Resonator Boundaries

### Quarter-Wave Resonator

Use a ladder with a grounded/coupled head and an open tail:

```julia
qwr = build_lc_ladder_line!(
    plan;
    id="qwr",
    head=qwr_ground,
    tail=qwr_open,
    spec=qwr_spec,
    head_termination=:short,
    tail_termination=:open,
)
```

Physical convention:

```text
The head side is grounded and may participate in coupling.
The tail side is open.
```

### Half-Wave Resonator

Use an open-open ladder or capacitively coupled endpoints:

```julia
filter = build_lc_ladder_line!(
    plan;
    id="purcell_filter",
    head=filter_head,
    tail=filter_tail,
    spec=filter_spec,
    head_termination=:open,
    tail_termination=:open,
)
```

In a point-coupled model, add capacitors from readout input/output nodes to the two resonator endpoints.

## EngineeringGraph

The builder records a semantic relation:

```text
relation_type = :transmission_line_ladder
from = head
to = tail
through = line id
parameters = length, reference section length, actual section lengths, n_sections, per-unit values, terminations
```

Primitive `series_inductor!`, `series_resistor!`, and `shunt_capacitor!` relations are also recorded, so notebooks can inspect both the physical generator and the compiled solver rows.
