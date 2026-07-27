---
aliases:
  - Intrinsic Interferometric Purcell Components
tags:
  - diataxis/reference
  - audience/contributor
  - topic/julia-core
status: draft
owner: docs-team
audience: contributor
scope: Candidate V1.1 filter-owned C0r update to the reusable intrinsic interferometric Purcell contracts.
version: v1.1.0-candidate
last_updated: 2026-07-26
updated_by: codex
---

# Intrinsic Interferometric Purcell Components

This `CONVERGING` V1.1 candidate separates three reusable Plan-level components.
The filter variants contain no feedline or external port. They expose the
filter-resonator IDC attachment so an enclosing circuit can add its own
feedline.

## V1 interfaces

| Component | Public attachments | Owned topology |
| --- | --- | --- |
| `InterdigitatedCapacitor` | `terminal_1`, `terminal_2` | `C1g`, `C2g`, and mutual `C12` |
| `IntrinsicInterferometricPurcellFilter` | `readout_attachment`, `feedline_attachment` | Two grounded-head/open-tail quarter-wave resonators, one finite MTL window, one complete IDC, and filter-owned `C0r` |
| `IntrinsicInterferometricPurcellFilterWithQubit` | `island_1`, `island_2`, `feedline_attachment` | The filter, including its `C0r`, plus a linearized floating qubit |

Julia Core owns electrical topology and exported schematic intent. The Python
Schemdraw library owns only the visual classes and renderer mapping. Committed
`schematic_export.json` fixtures are generated from the Julia examples; the
diagram scripts must not reconstruct circuit semantics manually.

## Interdigitated capacitor

The equivalent keeps all three positive capacitor branches. It is not reduced
to one scalar coupling capacitance.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../assets/circuit_draw/reusable_components/interdigitated_capacitor/diagram.dark.svg" />
  <img alt="Three-branch interdigitated capacitor equivalent" src="../../assets/circuit_draw/reusable_components/interdigitated_capacitor/diagram.light.svg" />
</picture>

## Intrinsic interferometric Purcell filter

The readout and filter QWRs share a finite MTL coupling window. The filter open
tail terminates at IDC terminal 1; IDC terminal 2 is the exposed
`feedline_attachment`. The filter also owns `C0r` from `readout_attachment` to
ground. `C0r = 0` is the default and omits the physical branch; a positive
finite value emits exactly one shunt-capacitor branch. No feedline is drawn or
compiled inside this component.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../assets/circuit_draw/reusable_components/intrinsic_interferometric_purcell_filter/diagram.dark.svg" />
  <img alt="Intrinsic interferometric Purcell filter without feedline" src="../../assets/circuit_draw/reusable_components/intrinsic_interferometric_purcell_filter/diagram.light.svg" />
</picture>

## Filter with qubit

The second composite reuses the filter and adds the linearized floating-qubit
branches at `readout_attachment`. It reuses the filter-owned `C0r` and never
stamps another branch. Its optional `c0r_f` keyword remains only as a
compatibility assertion: when supplied, it must exactly match the value used
to build the filter.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../assets/circuit_draw/reusable_components/intrinsic_interferometric_purcell_filter_with_qubit/diagram.dark.svg" />
  <img alt="Intrinsic interferometric Purcell filter with floating qubit and no feedline" src="../../assets/circuit_draw/reusable_components/intrinsic_interferometric_purcell_filter_with_qubit/diagram.light.svg" />
</picture>

## Failure behavior and limits

- Empty IDs, repeated public endpoints, invalid line/window geometry, and
  non-positive IDC branches fail in Julia Core.
- Intrinsic-filter construction rejects any MTL orientation other than
  `same_direction`.
- Negative or non-finite filter `C0r` fails before topology is added.
- The filter-with-qubit builder rejects a filter from another `CircuitPlan`.
- A filter-with-qubit `c0r_f` compatibility assertion that differs from the
  filter-owned value fails with a migration-oriented validation error.
- These classes do not own a feedline, port resistance, simulation intent,
  layout geometry, electromagnetic extraction, or nonlinear qubit dynamics.
- Existing D3 numerical workflows still accept scalar `Cext`; migrating those
  workflows to a qualified three-branch IDC artifact is a separate semantic
  scope.
- Durable tests remain unchanged while the V1.1 ownership update is
  `CONVERGING`; existing tests may be run only as diagnostic evidence.

## Schemdraw pipeline findings

The three diagrams in this V1 use the complete path:

```text
Julia builder
-> schematic_export.json
-> load_schematic_export()
-> component-type mapping
-> reusable Schemdraw component
-> light/dark SVG
```

The V1.1 candidate renders the distributed pair as five visual transmission-line
components: four plain CPW tiles plus one finite two-track MTL tile. The
electrical projection therefore contains six through-spans. The Julia export
records two tracks, four plain segments, and one coupled span; the renderer
records the branches emitted by the Schemdraw helpers. During convergence, a
one-time multiset comparison checks both projections, terminal exposure,
conditional `C0r`, and the final PNG hashes.

The pipeline is usable but not yet self-sealing:

- Four older transmission-line diagrams still construct Python components
  directly instead of consuming a Julia export.
- The renderer currently consumes `render_hints.schemdraw`; exported
  components, relations, terminals, tracks, segments, and coupled spans remain
  independent audit evidence rather than automatic drawing input.
- Manifest validation checks that `core_export_fixture` exists, but does not
  prove it is fresh or consumed by `draw.py`.
- The Python loader does not yet reject an unsupported export schema version,
  and Julia/Python component-type names can drift without a shared gate.

Future pipeline hardening is a separate scope: promote the temporary visual
Netlist comparison only after Human acceptance, add schema/component-type
validation, make export freshness and fixture consumption required checks, and
migrate the four bypass diagrams. Generic graph auto-layout remains excluded
until its layout semantics are defined separately.

## Semantic status

- Scope: Filter-owned default-zero `C0r` and its reuse by
  `IntrinsicInterferometricPurcellFilterWithQubit`, plus its five-component
  export-backed Schemdraw projection.
- Prior state: `STABILIZED` V1.
- Current state: `CONVERGING` V1.1 candidate because `C0r` ownership and the
  public builder contract changed.
- Reopening instruction: the Human requested that the filter own a default-zero
  `C0r` for later composition.
- Test policy: `no_test_writes`; existing tests are diagnostic only.
- Acceptance status: not yet requested for this V1.1 candidate.
