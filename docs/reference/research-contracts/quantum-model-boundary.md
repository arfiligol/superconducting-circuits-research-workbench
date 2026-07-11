---
aliases:
 - Quantum Model Boundary
 - Quantum simulation boundary
tags:
 - diataxis/reference
 - audience/team
 - sot/true
 - topic/research-contracts
status: stable
owner: docs-team
audience: team
scope: Placement rules for potential quantum-model and dynamics tools without expanding Julia Core ownership.
version: v1.1.0
last_updated: 2026-07-10
updated_by: codex
title: Quantum Model Boundary
description: Defines where quantum modeling, pulse simulation, and dynamics tools may live without contaminating Julia Core.
sidebar:
 label: Quantum Model Boundary
 order: 40
---

# Quantum Model Boundary

Reusable circuit-quantization semantics are owned by the SCQ_Design Knowledge
Base:

- [Canonical knowledge: Circuit Lagrangian, Hamiltonian, and Quantization](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/quantum-circuits/circuit-lagrangian-hamiltonian-quantization.qmd)

Quantum modeling begins only after circuit or equivalent-circuit parameters
are explicit. It does not change Julia Core ownership.

## Current Capability

The Workbench currently has no quantum-model package and no quantum-model
notebook. The tools below have permitted future placement; this table does not
claim that they are installed or executable in the current repository.

## Tool Position

| Tool | Permitted placement if implemented |
| --- | --- |
| scqubits | isolated Python notebook first; future separate Python quantum package only after its API stabilizes |
| QuTiP | isolated Python notebook for time evolution or open-system dynamics |
| qutip-qip | isolated Python notebook for pulse-level or processor-style studies |
| QuantumToolbox.jl | isolated Pluto notebook or future separate Julia quantum package |
| QuantumOptics.jl | isolated Pluto notebook or future separate Julia quantum package |

## Allowed Placement

| Work | Placement |
| --- | --- |
| scqubits/QuTiP/qutip-qip exploration | Python notebooks |
| qutip-qip pulse simulation | Python notebooks |
| stable Python quantum helpers | future separate Python quantum package |
| Julia operator/dynamics experiments | isolated Pluto notebook or future separate Julia quantum package |
| reusable circuit authoring | Julia Core |
| fitting and matrix algorithms | Python Analysis Core |

## Forbidden Placement

Julia Core must not depend on:

- scqubits
- QuTiP
- qutip-qip
- QuantumToolbox.jl
- QuantumOptics.jl
- gdsfactory
- gsim
- gplugins
- qpdk
- PythonCall
- notebook-only analysis dependencies

## Related

- [Equivalent Circuit To Quantum Model](../../workflows/equivalent-circuit-to-quantum-model/index.md)
- [Quantum Dynamics / Pulse Simulation](../../workflows/quantum-dynamics-pulse-simulation/index.md)
- [Julia Core](../julia-core/index.mdx)
- [Python Core](../core/python-core.mdx)
