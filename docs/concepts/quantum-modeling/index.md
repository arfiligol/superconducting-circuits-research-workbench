---
aliases:
 - Quantum Modeling
tags:
 - diataxis/explanation
 - audience/team
 - topic/quantum-modeling
status: stable
owner: docs-team
audience: team
scope: Workbench handoffs from equivalent-circuit artifacts to canonical SCQ_Design circuit-quantization knowledge and intended quantum-tool placement.
version: v1.1.0
last_updated: 2026-07-10
updated_by: codex
title: Quantum Modeling
description: Concepts that support Route 3, after an equivalent circuit exists and before dynamics begin.
sidebar:
 label: Overview
 order: 10
---

# Quantum Modeling

Reusable circuit-quantization knowledge is owned by the SCQ_Design Super Repo:

- [Canonical knowledge: Circuit Lagrangian, Hamiltonian, and Quantization](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/quantum-circuits/circuit-lagrangian-hamiltonian-quantization.qmd)

This section records Workbench-specific artifact requirements and intended tool
placement for Route 3. It is not a second physics Knowledge Base.

## Current Capability

The Workbench currently has no quantum-model package and no quantum-model
notebook. These pages define the intended route and review boundary; they do
not expose an executable scqubits or dynamics workflow.

## Page Map

| Page | Use it when |
| --- | --- |
| [Equivalent Circuit To Hamiltonian](equivalent-circuit-to-hamiltonian.md) | You need the scqubits-style modeling boundary and circuit quantization references. |
| [Floating Qubit Study](floating-qubit-study.mdx) | You need context for floating-qubit admittance and quantization studies. |

## Boundary

If implemented, scqubits-style circuit modeling belongs in an isolated Python
notebook first. Julia quantum-dynamics packages may be evaluated only in an
isolated notebook and must not become Julia Core dependencies.

## References

- [scqubits documentation](https://scqubits.readthedocs.io/)
- [scqubits Circuit API](https://scqubits.readthedocs.io/en/latest/api-doc/_autosummary/scqubits.core.circuit.Circuit.html)
