---
aliases:
 - Equivalent Circuit Model Contract
 - Equivalent circuit contract
tags:
 - diataxis/reference
 - audience/team
 - sot/true
 - topic/research-contracts
status: stable
owner: docs-team
audience: team
scope: Required fields and semantics for fitted equivalent circuit models.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Equivalent Circuit Model Contract
description: Defines how fitted equivalent circuit models must remain reviewable and reusable.
sidebar:
 label: Equivalent Circuit Model Contract
 order: 30
---

# Equivalent Circuit Model Contract

An equivalent circuit model is a reviewed reduction of a distributed or simulated response into a reusable parameter set. It is the meeting point between reusable CircuitPlan research and external FEM-result analysis.

## Required Content

| Field | Requirement |
| --- | --- |
| model family | RLC, RLGC, coupling model, mode extraction, or another named family |
| parameters | values with explicit units and physical meaning |
| source traces | references to the normalized S/Y/Z trace package used for fitting |
| fit range | frequency range and any excluded samples |
| metrics | residual, RMSE, quality score, or another explicit fit quality measure |
| model trace | reconstructed trace for visual comparison when available |
| assumptions | topology, port convention, grounding, symmetry, and reduction assumptions |
| provenance | upstream source and analysis notebook or package version |

## Accepted Model Families

| Family | Typical use |
| --- | --- |
| RLC | compact resonance or impedance/admittance reduction |
| RLGC | distributed transmission-line equivalent |
| coupling model | mutual capacitance, mutual inductance, coupling window, or effective coupling |
| mode model | mode frequencies, linewidths, loss, and mode coupling descriptors |

## Handoff

The model should be usable by at least one downstream consumer:

- Julia Core study that compares a reusable CircuitPlan response against the fitted equivalent model
- Python Analysis Core report that validates fit quality
- scqubits/QuTiP/qutip-qip study that uses fitted parameters as quantum-model or dynamics input
- QuTiP/qutip-qip or isolated Julia dynamics study that consumes explicit Hamiltonian/operator parameters

## Related

- [Equivalent Circuit To Quantum Model](../../workflows/equivalent-circuit-to-quantum-model/index.md)
- [Quantum Dynamics / Pulse Simulation](../../workflows/quantum-dynamics-pulse-simulation/index.md)
- [Quantum Model Boundary](quantum-model-boundary.md)
