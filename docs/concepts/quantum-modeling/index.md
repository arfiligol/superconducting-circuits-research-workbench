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
scope: Knowledge base for equivalent-circuit to Hamiltonian modeling and scqubits-style quantum model boundaries.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Quantum Modeling
description: Concepts that support Route 3, after an equivalent circuit exists and before dynamics begin.
sidebar:
 label: Overview
 order: 10
---

# Quantum Modeling

This knowledge base supports Route 3. It explains how explicit circuit parameters become Hamiltonians, spectra, matrix elements, coherence estimates, or operator handoff artifacts.

## Page Map

| Page | Use it when |
| --- | --- |
| [Equivalent Circuit To Hamiltonian](equivalent-circuit-to-hamiltonian.md) | You need the scqubits-style modeling boundary and circuit quantization references. |
| [Floating Qubit Study](floating-qubit-study.mdx) | You need context for floating-qubit admittance and quantization studies. |

## Boundary

scqubits is the canonical Python route for superconducting-qubit modeling. Julia quantum dynamics packages can run isolated operator experiments, but they do not replace the scqubits circuit-modeling layer and must not become Julia Core dependencies.

## References

- [scqubits documentation](https://scqubits.readthedocs.io/)
- [scqubits Circuit API](https://scqubits.readthedocs.io/en/latest/api-doc/_autosummary/scqubits.core.circuit.Circuit.html)
- [Koch et al., Charge-insensitive qubit design derived from the Cooper pair box](https://arxiv.org/abs/cond-mat/0703002)
- [Nigg et al., Black-box superconducting circuit quantization](https://link.aps.org/doi/10.1103/PhysRevLett.108.240502)
- [Minev et al., Energy-participation quantization of Josephson circuits](https://www.nature.com/articles/s41534-021-00461-8)
