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
scope: Workbench tool and artifact handoff from equivalent-circuit parameters to canonical SCQ_Design circuit-quantization knowledge.
version: v1.1.0
last_updated: 2026-07-10
updated_by: codex
title: Equivalent Circuit To Hamiltonian
sidebar:
 label: Equivalent Circuit To Hamiltonian
 order: 20
---

# Equivalent Circuit To Hamiltonian

The reusable derivation from circuit coordinates to a quantum Hamiltonian is
owned by the SCQ_Design Knowledge Base:

- [Canonical knowledge: Circuit Lagrangian, Hamiltonian, and Quantization](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/quantum-circuits/circuit-lagrangian-hamiltonian-quantization.qmd)

This Workbench page owns only the intended tool placement and the information
that an equivalent-circuit artifact must carry before that handoff.

## Current Capability

There is currently no Workbench quantum-model package and no quantum-model
notebook that executes this route. The shape below is an intended workflow, not
an executable capability.

## Intended Handoff Shape

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

The Hamiltonian handoff does not change Julia Core ownership. Julia Core can
produce reusable circuit plans and response outputs. If an executable
scqubits-based study is added, it belongs in a Python notebook first; a Python
quantum package is justified only after a repeated helper surface becomes
stable.

## References

- [scqubits documentation](https://scqubits.readthedocs.io/)
- [scqubits custom circuit guide](https://scqubits.readthedocs.io/en/latest/guide/circuit/ipynb/custom_circuit_define.html)
- [scqubits Circuit API](https://scqubits.readthedocs.io/en/latest/api-doc/_autosummary/scqubits.core.circuit.Circuit.html)
- [scqubits HilbertSpace guide](https://scqubits.readthedocs.io/en/v4.1/guide/hilbertspace/ipynb/hilbertspace.html)
