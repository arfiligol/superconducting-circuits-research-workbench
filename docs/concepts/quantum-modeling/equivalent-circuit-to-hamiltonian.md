---
aliases:
 - Equivalent Circuit To Hamiltonian
 - Hamiltonian handoff
tags:
 - diataxis/explanation
 - audience/team
 - topic/quantum-modeling
status: stable
owner: docs-team
audience: team
scope: How equivalent-circuit parameters become Hamiltonian inputs without expanding Julia Core.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Equivalent Circuit To Hamiltonian
sidebar:
 label: Equivalent Circuit To Hamiltonian
 order: 20
---

# Equivalent Circuit To Hamiltonian

An equivalent circuit is useful for quantum modeling only when its variables, units, topology, and assumptions are explicit enough to become Hamiltonian inputs. This page supports Route 3, where fitted or authored circuit parameters become scqubits-style models.

## Handoff Shape

```text
equivalent circuit model
  -> named nodes, branches, energies, capacitances, inductances, Josephson terms
  -> scqubits circuit, subsystem, or custom circuit representation
  -> Hamiltonian, spectra, matrix elements, coherence estimates
```

## What Must Be Explicit

- degrees of freedom and node/branch convention
- capacitance, inductance, Josephson energy, and external flux units
- grounding and constraints
- mode or branch reduction assumptions
- parameter provenance and fit uncertainty
- expected operating range

## Placement Rule

The Hamiltonian handoff does not change Julia Core ownership. Julia Core can produce reusable circuit plans and response outputs. scqubits modeling belongs in Python notebooks first, then a future Python quantum package if the repeated helper surface becomes stable.

## References

- [scqubits documentation](https://scqubits.readthedocs.io/)
- [scqubits custom circuit guide](https://scqubits.readthedocs.io/en/latest/guide/circuit/ipynb/custom_circuit_define.html)
- [scqubits Circuit API](https://scqubits.readthedocs.io/en/latest/api-doc/_autosummary/scqubits.core.circuit.Circuit.html)
- [scqubits HilbertSpace guide](https://scqubits.readthedocs.io/en/v4.1/guide/hilbertspace/ipynb/hilbertspace.html)
- [Koch et al., Charge-insensitive qubit design derived from the Cooper pair box](https://arxiv.org/abs/cond-mat/0703002)
- [Nigg et al., Black-box superconducting circuit quantization](https://link.aps.org/doi/10.1103/PhysRevLett.108.240502)
- [Minev et al., Energy-participation quantization of Josephson circuits](https://www.nature.com/articles/s41534-021-00461-8)
