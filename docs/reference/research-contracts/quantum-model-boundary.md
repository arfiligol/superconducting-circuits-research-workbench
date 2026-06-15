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
scope: Boundary rules for scqubits, QuTiP, qutip-qip, QuantumToolbox.jl, QuantumOptics.jl, and Julia Core.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Quantum Model Boundary
description: Defines where quantum modeling, pulse simulation, and dynamics tools may live without contaminating Julia Core.
sidebar:
 label: Quantum Model Boundary
 order: 40
---

# Quantum Model Boundary

Quantum modeling begins after the circuit or equivalent circuit parameters are explicit. It does not change Julia Core ownership.

## Tool Position

| Tool | Position in this repo |
| --- | --- |
| scqubits | Python route for superconducting-qubit models, custom circuit YAML, spectra, matrix elements, coherence estimates, and QuTiP interop |
| QuTiP | Python route for time evolution, open-system dynamics, and pulse-style studies |
| qutip-qip | Python route for pulse-level and processor-style quantum information simulation |
| QuantumToolbox.jl | optional Julia-native operator/dynamics route, isolated from Julia Core |
| QuantumOptics.jl | optional Julia-native open/closed quantum-system route, isolated from Julia Core |

There is no official Julia scqubits equivalent in the current public ecosystem. Julia quantum dynamics packages are useful, but they do not replace scqubits' superconducting-circuit modeling layer.

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
