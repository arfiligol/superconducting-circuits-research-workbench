---
aliases:
 - Isolated Julia Dynamics
tags:
 - diataxis/how-to
 - audience/user
 - topic/quantum-dynamics
status: draft
owner: docs-team
audience: user
scope: Optional isolated Julia dynamics route that must not expand Julia Core duties.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Isolated Julia Dynamics
sidebar:
 label: Isolated Julia Dynamics
 order: 40
---

# Isolated Julia Dynamics

Use this workflow only when the research question benefits from a Julia-native operator or dynamics package. This is an optional research lane, not a Julia Core expansion.

## Procedure Shape

1. Start from an explicit Hamiltonian/operator specification.
2. Create an isolated Pluto notebook or separate experimental Julia package.
3. Use QuantumToolbox.jl or QuantumOptics.jl for the operator/dynamics question.
4. Export the result evidence back as plots, tables, or normalized result artifacts.
5. Keep reusable component and plan authoring in Julia Core, not in the dynamics notebook.

## Boundary

QuantumToolbox.jl and QuantumOptics.jl can be useful for time evolution and open-system experiments, but they do not replace scqubits for superconducting-qubit circuit modeling. They must not be added as Julia Core dependencies.

## References

- [QuantumToolbox.jl documentation](https://qutip.org/QuantumToolbox.jl/stable/)
- [QuantumOptics.jl documentation](https://docs.qojulia.org/)
- [QuantumOptics.jl time evolution](https://docs.qojulia.org/timeevolution/timeevolution/)
