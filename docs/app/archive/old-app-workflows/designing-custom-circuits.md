---
aliases:
 - Designing Custom Circuits
 - Custom circuit design
tags:
 - diataxis/tutorial
 - audience/user
 - topic/circuit-design
status: stable
owner: docs-team
audience: user
scope: Design guidelines for custom circuits from source netlist to simulatable setup
version: v0.1.0
last_updated: 2026-03-20
updated_by: codex
sidebar:
 label: Designing Custom Circuits
 order: 50
---

# Designing Custom Circuits

> Legacy reference only. This page preserves old Schema Editor workflow context under Product App Archive and is not part of the current research-first workflow path.

This page focuses on the design and verification checklist when customizing circuits.

## Checklist

1. `components` first defines the reusable parameter interface (`default`/`value_ref`).
2. `topology` only handles connections and does not mix parameter semantics.
3. Prioritize the use of `repeat` to reduce post-deployment maintenance costs.
4. Use Expanded Netlist Preview for deterministic verification.
5. Verify the base mode on the Simulation side first, and then enable sideband/post-processing.

## Example: FloatingQubitWithXYLine

This is an example of dual port floating qubit and XY line. Its characteristics are:

1. `R50` serves as the matching resistor for the two ports.
2. `L_jun` extracts adjustable parameters through `parameters` and `value_ref`.
3. `C_xy1`, `C_xy2` couple the qubit node to the third port.

Can be used directly as a JSON source for Schema Editor:

```json
{
 "name": "FloatingQubitWithXYLine",
 "components": [
  { "name": "R50", "unit": "Ohm", "default": 50 },
  { "name": "C_q", "unit": "pF", "default": 0.05814 },
  { "name": "C_g1", "unit": "pF", "default": 0.10254 },
  { "name": "C_g2", "unit": "pF", "default": 0.10189 },
  { "name": "C_xy1", "unit": "pF", "default": 0.00017 },
  { "name": "C_xy2", "unit": "pF", "default": 0.00075 },
  { "name": "L_jun", "unit": "nH", "value_ref": "L_jun" }
 ],
 "topology": [
  ["P1", "1", "0", 1],
  ["R_p1", "1", "0", "R50"],
  ["P2", "2", "0", 2],
  ["R_p2", "2", "0", "R50"],
  ["P3", "3", "0", 3],
  ["R_p3", "3", "0", "R50"],
  ["C_q", "1", "2", "C_q"],
  ["L_jun1", "1", "2", "L_jun"],
  ["L_jun2", "1", "2", "L_jun"],
  ["C_g1", "1", "0", "C_g1"],
  ["C_g2", "2", "0", "C_g2"],
  ["C_xy1", "1", "3", "C_xy1"],
  ["C_xy2", "2", "3", "C_xy2"]
 ],
 "parameters": [
  { "name": "L_jun", "default": 24, "unit": "nH" }
 ]
}
```

## Validation Notes

1. `name` will be synchronized to the canonical source name in Schema Editor.
2. `parameters.L_jun` corresponds to `components[].value_ref`, which is suitable for subsequent sweeps.
3. It is recommended to check whether the coupling between the port number and the node `3` is as expected in Expanded Netlist Preview before sending it to Simulation.

## Related

- [Circuit Netlist](../old-app-contracts/circuit-netlist.mdx)
- [Schema Editor UI](../../frontend/definition/schema-editor.mdx)
- [Promote Pluto Prototype To Reusable Core](../../../workflows/reusable-circuit-authoring/promote-pluto-prototype-to-reusable-core.md)
