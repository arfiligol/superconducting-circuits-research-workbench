---
aliases:
 - Pulse-Level Dynamics
tags:
 - diataxis/explanation
 - audience/team
 - topic/quantum-dynamics
status: stable
owner: docs-team
audience: team
scope: Conceptual boundary for time evolution, open-system dynamics, and pulse-level simulation.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Pulse-Level Dynamics
sidebar:
 label: Pulse-Level Dynamics
 order: 20
---

# Pulse-Level Dynamics

Pulse-level simulation asks what a Hamiltonian or operator model does under drives, controls, dissipation, and time evolution. It is downstream from equivalent-circuit and Hamiltonian modeling.

## Tool Roles

| Tool family | Role |
| --- | --- |
| QuTiP | Python time evolution, master equations, and operator dynamics |
| qutip-qip | Python pulse-level and processor-style quantum information simulations |
| QuantumToolbox.jl | Julia QuTiP-like dynamics experiments in an isolated lane |
| QuantumOptics.jl | Julia open/closed quantum-system experiments in an isolated lane |

## Boundary

This route is not an extension of Julia Core. It consumes explicit Hamiltonians and operators. Reusable pulse or dynamics helpers should live in notebooks first, then in a future quantum package if repeated use justifies it.

## References

- [QuTiP documentation](https://qutip.org/)
- [QuTiP time-dependent dynamics guide](https://qutip.readthedocs.io/en/latest/guide/dynamics/dynamics-time.html)
- [qutip-qip processor guide](https://qutip-qip.readthedocs.io/en/stable/qip-processor.html)
- [Li et al., Pulse-level noisy quantum circuits with QuTiP](https://quantum-journal.org/papers/q-2022-01-24-630/)
- [QuantumToolbox.jl documentation](https://qutip.org/QuantumToolbox.jl/stable/)
- [QuantumOptics.jl time evolution](https://docs.qojulia.org/timeevolution/timeevolution/)
