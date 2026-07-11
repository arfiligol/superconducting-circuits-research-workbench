---
aliases:
 - Equivalent Circuit To Quantum Model
 - Quantum model workflow
tags:
 - diataxis/how-to
 - audience/user
 - topic/analysis
status: stable
owner: docs-team
audience: user
scope: Intended Workbench workflow from fitted equivalent-circuit artifacts to canonical circuit-quantization semantics and isolated quantum tools.
version: v1.1.0
last_updated: 2026-07-10
updated_by: codex
title: Equivalent Circuit To Quantum Model
description: Define the intended handoff from equivalent-circuit parameters to an isolated quantum-model lane.
sidebar:
 label: Equivalent Circuit To Quantum Model
 order: 10
---

# Equivalent Circuit To Quantum Model

Use the canonical SCQ_Design node for the reusable circuit-coordinate,
Lagrangian, Hamiltonian, constraint, and quantization semantics:

- [Canonical knowledge: Circuit Lagrangian, Hamiltonian, and Quantization](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/quantum-circuits/circuit-lagrangian-hamiltonian-quantization.qmd)

This Workbench page defines the intended Route 3 handoff after a distributed or
simplified circuit has been reduced into an explicit equivalent-circuit model.
It stops before Route 4 time evolution and pulse studies.

## Current Capability

There is currently no quantum-model package and no quantum-model notebook in
this repository. The route below is a prose contract for future implementation,
not an executable workflow.

## Intended Python Route

If implemented, use this isolated Python shape for scqubits-style
superconducting-qubit modeling:

```text
reviewed equivalent-circuit artifact
  -> scqubits circuit, subsystem, or custom circuit inputs
  -> Hamiltonian, spectra, matrix elements, coherence estimates
  -> HilbertSpace or exported operator data for dynamics
```

Start in a Python notebook. Add a separate Python quantum package only if a
repeated, reviewed helper surface becomes stable.

## Optional Julia Operator Route

Julia packages such as QuantumToolbox.jl or QuantumOptics.jl may be evaluated
for operator-level experiments or Pluto-visible studies. They are not scqubits
replacements, are not current Workbench capabilities, and must not be added to
Julia Core.

The safe placement is:

```text
reviewed equivalent-circuit artifact
  -> explicit Hamiltonian/operator spec
  -> isolated Julia quantum notebook or future separate Julia quantum package
  -> result package or report evidence
```

## Boundary

The quantum model layer consumes equivalent-circuit parameters. It does not change the ownership of Julia Core. Julia Core stays responsible for reusable component/plan authoring and JosephsonCircuits.jl response generation. Pulse-level and open-system time evolution belongs in [Quantum Dynamics / Pulse Simulation](../quantum-dynamics-pulse-simulation/index.md).

## References

- [scqubits documentation](https://scqubits.readthedocs.io/)
- [scqubits custom circuit guide](https://scqubits.readthedocs.io/en/latest/guide/circuit/ipynb/custom_circuit_define.html)

## Related

- [Quantum Model Boundary](../../reference/research-contracts/quantum-model-boundary.md)
- [Notebook Roles](../../reference/research-contracts/notebook-roles.md)
- [Equivalent Circuit To Hamiltonian](../../concepts/quantum-modeling/equivalent-circuit-to-hamiltonian.md)
- [Circuit Research Routes](../../concepts/gdsfactory-compatible-artifacts/circuit-research-routes.md)
