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
scope: Workflow for using fitted equivalent circuit parameters as quantum-model and Hamiltonian inputs.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Equivalent Circuit To Quantum Model
description: Hand equivalent circuit parameters to scqubits or another isolated quantum-model lane.
sidebar:
 label: Equivalent Circuit To Quantum Model
 order: 10
---

# Equivalent Circuit To Quantum Model

Use this workflow after a distributed or simplified circuit has been reduced into an explicit equivalent circuit model. The upstream source can be a Julia Core `CircuitPlan` response or an external FEM/simulation result. This workflow stops at quantum-model construction and Hamiltonian handoff; time evolution and pulse studies are Route 4.

## Main Python Route

The Python route is canonical for scqubits-style superconducting-qubit modeling:

```text
EquivalentCircuitFit
  -> scqubits circuit, subsystem, or custom circuit inputs
  -> Hamiltonian, spectra, matrix elements, coherence estimates
  -> HilbertSpace or exported operator data for dynamics
```

Use this route when the work needs scqubits custom circuit YAML, qubit classes, parameter sweeps, matrix elements, coherence estimates, or QuTiP interop. In this repo, that belongs in Python notebooks first and a future separate Python quantum package if the API stabilizes.

## Optional Julia Operator Route

Julia packages such as QuantumToolbox.jl or QuantumOptics.jl can be useful for operator-level experiments or Pluto-visible studies. They are not scqubits replacements, and they should not be added to Julia Core.

The safe placement is:

```text
EquivalentCircuitFit
  -> explicit Hamiltonian/operator spec
  -> isolated Julia quantum notebook or future separate Julia quantum package
  -> result package or report evidence
```

## Boundary

The quantum model layer consumes equivalent-circuit parameters. It does not change the ownership of Julia Core. Julia Core stays responsible for reusable component/plan authoring and JosephsonCircuits.jl response generation. Pulse-level and open-system time evolution belongs in [Quantum Dynamics / Pulse Simulation](../quantum-dynamics-pulse-simulation/index.md).

## References

- [scqubits documentation](https://scqubits.readthedocs.io/)
- [scqubits custom circuit guide](https://scqubits.readthedocs.io/en/latest/guide/circuit/ipynb/custom_circuit_define.html)
- [Koch et al., Charge-insensitive qubit design derived from the Cooper pair box](https://arxiv.org/abs/cond-mat/0703002)
- [Nigg et al., Black-box superconducting circuit quantization](https://link.aps.org/doi/10.1103/PhysRevLett.108.240502)
- [Minev et al., Energy-participation quantization of Josephson circuits](https://www.nature.com/articles/s41534-021-00461-8)

## Related

- [Quantum Model Boundary](../../reference/research-contracts/quantum-model-boundary.md)
- [Notebook Roles](../../reference/research-contracts/notebook-roles.md)
- [Equivalent Circuit To Hamiltonian](../../concepts/quantum-modeling/equivalent-circuit-to-hamiltonian.md)
- [Circuit Research Routes](../../concepts/gdsfactory-compatible-artifacts/circuit-research-routes.md)
