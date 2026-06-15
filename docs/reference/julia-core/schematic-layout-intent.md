---
aliases:
 - Schematic Layout Intent
 - SchematicLayoutIntent
 - SchematicExportSpec
tags:
 - diataxis/reference
 - audience/contributor
 - sot/true
 - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Renderer-neutral schematic layout intent and schematic export contract for Julia Core authoring.
version: v1.0.0
last_updated: 2026-05-31
updated_by: codex
---

# Schematic Layout Intent

`SchematicLayoutIntent` describes how a circuit should be drawn. It is separate from [`EngineeringGraph`](engineering-graph.md), which describes what the circuit is.

Use layout intent when a schematic must preserve engineering shape: CPW tracks, coupled windows, segment labels, boundary node labels, port sides, open ends, and ground symbols.

## Layer Boundary

Engineering semantics and drawing semantics answer different questions.

| Layer | Question | Examples |
| --- | --- | --- |
| `EngineeringGraph` | What is this circuit? | readout line, QWR, coupled window, port roles, component hierarchy |
| `SchematicLayoutIntent` | How should this circuit be drawn? | top track, bottom track, aligned span, left port, right ground, A/B/C/D labels |
| `SchematicExportSpec` | What should a renderer receive? | graph records, tracks, terminals, labels, renderer-neutral hints |

Solver compilation uses electrical topology and parameter values. It does not use drawing layout.

Schemdraw is one renderer for `SchematicExportSpec`. Julia Core packages import no Python renderer packages and do not expose Schemdraw-shaped circuit semantics.

## Layout Grammar

Use these concepts to express renderer-neutral schematic intent.

| Concept | Meaning |
| --- | --- |
| `group` | logical or visual container for related schematic items |
| `track` | visual lane for a transmission-line-like object |
| `segment` | finite interval on a track, usually measured from the line head |
| `coupled_span` | aligned interval between tracks that represents a coupled window |
| `terminal` | visible end marker such as port, ground, open, or continuation |
| `node_label` | visible label for a point such as `A`, `B`, `C`, or `D` |
| `segment_label` | label for a track interval such as `ℓ_c` or `ℓ_r` |
| `anchor` | non-electrical drawing or report reference point |
| `relative_order` | visual ordering such as top/bottom or left/right |
| `orientation` | drawing direction such as left-to-right or top-to-bottom |

`group` is a semantic container. `track` is a schematic lane. Do not use `group` to imply physical placement.

Anchors are not electrical endpoints. If an outside circuit can connect to a point, model that point as a pin, tap, or probe in the component interface, then reference it from layout intent.

## Track-Based CPW / MTL Layout

For CPW and MTL structures, layout intent should preserve the line geometry that engineers expect to see:

- parallel tracks for coupled lines;
- distance-based segments measured from each head;
- coupled spans aligned across tracks;
- visible terminals for ports, grounds, opens, and continuations;
- node labels at coupled-window boundaries;
- segment labels for physical lengths.

The layout intent references semantic objects created by the circuit authoring layer. It does not create electrical relations by itself.

## Two Parallel CPWs With A Coupled Window

This circuit uses two transmission-line ladders and one finite MTL coupled window.

```julia
plan = @circuit "coupled-window-example" begin
  port1_node = external_node("port1")
  port2_node = external_node("port2")

  resonator_line = transmission_line!(
    id =:resonator_line,
    head = port1_node,
    tail = ground(),
    spec = resonator_spec,
    head_termination =:external,
    tail_termination =:grounded,
    breakpoints = [l_r_open, l_r_open + l_c],
    role =:resonator_path,
  )

  pump_line = transmission_line!(
    id =:pump_line,
    head = port2_node,
    tail = ground(),
    spec = pump_spec,
    head_termination =:external,
    tail_termination =:grounded,
    breakpoints = [l_p_open, l_p_open + l_c],
    role =:pump_or_readout_path,
  )

  window = couple_transmission_window!(
    id =:coupled_window,
    line1 = resonator_line,
    line2 = pump_line,
    start1 = l_r_open,
    start2 = l_p_open,
    length = l_c,
    model = coupled_window_model,
    role =:mtl_coupled_window,
  )

  port(:port1) do
    index = 1
    endpoint = port1_node
    resistance = 50.0
    role =:input
  end

  port(:port2) do
    index = 2
    endpoint = port2_node
    resistance = 50.0
    role =:input
  end
end
```

The schematic intent declares how those semantic objects should appear.

```julia
schematic!(plan; id =:paper_view) do
  track(:resonator_track) do
    line = resonator_line
    orientation =:left_to_right
    relative_order =:top
    color =:red
  end

  track(:pump_track) do
    line = pump_line
    orientation =:left_to_right
    relative_order =:bottom
    color =:blue
  end

  coupled_span(:middle_window) do
    relation = window
    track1 =:resonator_track
    track2 =:pump_track
    align =:start_and_end
    label = "ℓ_c"
    interface_nodes = (
      line1_start =:A,
      line1_end =:B,
      line2_start =:C,
      line2_end =:D,
    )
    render =:parallel_cpw_window
  end

  segment_label(:resonator_left) do
    line = resonator_line
    from = 0.0
    to = l_r_open
    label = "ℓᵒʳ"
  end

  segment_label(:resonator_right) do
    line = resonator_line
    from = l_r_open + l_c
    to = resonator_total_length
    label = "ℓˢʳ"
  end

  segment_label(:pump_left) do
    line = pump_line
    from = 0.0
    to = l_p_open
    label = "ℓᵒᵖ"
  end

  segment_label(:pump_right) do
    line = pump_line
    from = l_p_open + l_c
    to = pump_total_length
    label = "ℓˢᵖ"
  end

  terminal(:port1) do
    endpoint = port1_node
    side =:left
    kind =:port
    label = "1"
  end

  terminal(:port2) do
    endpoint = port2_node
    side =:left
    kind =:port
    label = "2"
  end

  terminal(:resonator_ground) do
    endpoint = ground()
    track =:resonator_track
    side =:right
    kind =:ground
  end

  terminal(:pump_ground) do
    endpoint = ground()
    track =:pump_track
    side =:right
    kind =:ground
  end
end
```

This is enough for a renderer to draw two horizontal CPW-like tracks, a middle coupled region, A/B/C/D boundary labels, left-side port numbers, right-side ground symbols, and length labels.

## SchematicExportSpec

`SchematicExportSpec` combines semantic graph data, layout intent, and renderer-neutral hints.

```julia
SchematicExportSpec(
  engineering_graph,
  layout_intent,
  components,
  relations,
  ports,
  groups,
  tracks,
  segments,
  coupled_spans,
  terminals,
  node_labels,
  segment_labels,
  anchors,
  render_hints,
)
```

The export should include enough information to draw CPW / MTL diagrams without reading solver rows:

```text
top track = resonator line
bottom track = pump or readout line
coupled span = middle window
boundary nodes = A/B/C/D
segment labels = ℓᵒʳ, ℓ_c, ℓˢʳ, ℓᵒᵖ, ℓˢᵖ
port labels = 1, 2
ground terminals = right-side grounds
```

Render hints describe presentation preferences, not circuit semantics. A renderer may map `render =:parallel_cpw_window` to its own drawing primitives, but the electrical meaning remains in the `EngineeringGraph` and `CircuitPlan`.

## Renderer Boundary

Renderer packages consume `SchematicExportSpec` and produce images, diagrams, or interactive views.

```text
Macro DSL
  -> canonical Core API
  -> CircuitPlan
  -> EngineeringGraph
  -> SchematicLayoutIntent
  -> SchematicExportSpec
  -> renderer

CircuitPlan
  -> compiler
  -> solver rows
```

Schemdraw belongs on the renderer side of this boundary. It consumes exported schematic data and emits a drawing artifact. It does not define component interfaces, coupling semantics, HB intent, or solver lowering.
Reusable Python Schemdraw visual components live in `core/python/circuit_libraries/schemdraw_circuit_library/`; they map renderer-neutral component records or render hints to drawings without becoming a second circuit model.

## Cross-Links

- [Engineering Graph](engineering-graph.md) defines the human-facing semantic graph.
- [Macro Authoring DSL](macro-authoring-dsl.md) defines the authoring surface that records semantics and layout intent.
- [Transmission Line Ladder](transmission-line-ladder.md) defines head/tail, section, and termination conventions for track-based layout.
- [Coupling Models](coupling-models.mdx) defines point coupling and finite MTL coupled-window semantics.
