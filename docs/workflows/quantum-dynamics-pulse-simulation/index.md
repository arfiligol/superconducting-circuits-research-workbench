---
aliases:
 - Quantum Dynamics / Pulse Simulation
 - Pulse simulation workflow
tags:
 - diataxis/how-to
 - audience/user
 - topic/quantum-dynamics
status: draft
owner: docs-team
audience: user
scope: Workflow route for time evolution, open-system dynamics, and pulse-level simulation after Hamiltonian construction.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Quantum Dynamics / Pulse Simulation
description: Use QuTiP and qutip-qip first, with Julia dynamics kept as an isolated optional lane.
sidebar:
 label: Overview
 order: 10
---

# Quantum Dynamics / Pulse Simulation

This route starts after Route 3 has produced a Hamiltonian, subsystem model, or explicit operator representation. It does not belong in Julia Core. It belongs in Python notebooks first, and only later in a separate quantum package if the API stabilizes.

```text
Hamiltonian or operator model
  -> time-dependent drive or pulse description
  -> QuTiP / qutip-qip simulation
  -> time traces, gate/pulse evidence, open-system diagnostics
  -> report or reusable quantum helper
```

## Page Map

| Page | Use it when |
| --- | --- |
| [QuTiP Dynamics](qutip-dynamics.md) | You need time evolution, open-system dynamics, or operator-level experiments. |
| [qutip-qip Pulse Simulation](qutip-qip-pulse-simulation.md) | You need pulse-level or processor-style simulation in the Python route. |
| [Isolated Julia Dynamics](isolated-julia-dynamics.md) | You need a Julia-native operator experiment without adding duties to Julia Core. |

## Boundary

This route consumes a Hamiltonian or operator model. It must not pull scqubits, QuTiP, qutip-qip, QuantumToolbox.jl, or QuantumOptics.jl into Julia Core. Julia Core remains the reusable circuit authoring and JosephsonCircuits.jl response layer.

## Related

- [Equivalent Circuit To Quantum Model](../equivalent-circuit-to-quantum-model/index.md)
- [Quantum Dynamics & Pulse Simulation Concepts](../../concepts/quantum-dynamics-pulse-simulation/index.md)
- [Quantum Model Boundary](../../reference/research-contracts/quantum-model-boundary.md)
