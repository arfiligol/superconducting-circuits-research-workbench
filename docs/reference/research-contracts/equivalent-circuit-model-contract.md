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
version: v1.5.0
last_updated: 2026-07-16
updated_by: codex
title: Equivalent Circuit Model Contract
description: Defines how fitted equivalent circuit models must remain reviewable and reusable.
sidebar:
 label: Equivalent Circuit Model Contract
 order: 30
---

# Equivalent Circuit Model Contract

An equivalent circuit model is a reviewed reduction of a distributed or simulated response into a reusable parameter set. It is the meeting point between reusable CircuitPlan research and external FEM-result analysis.

When the model is intended for a quantum Hamiltonian, use the canonical
coordinate, constraint, Lagrangian, Hamiltonian, and quantization semantics:

- [Canonical knowledge: Circuit Models to Bare Coordinates, Open EOM, and Normal Modes](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/quantum-circuits/physical-circuit-coordinates-node-flux-basis.qmd)
- [Canonical knowledge: Circuit Lagrangian, Hamiltonian, and Quantization](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/quantum-circuits/circuit-lagrangian-hamiltonian-quantization.qmd)

When the model is a distributed line built directly from field-extracted
matrices, use the canonical terminal-basis and lowering semantics:

- [Canonical knowledge: Multiconductor RLGC Matrices](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd)

When a frequency, coupling, linewidth, or notch is extracted from a network
response, use the canonical response and mode-layer semantics:

- [Canonical knowledge: Network Trace Views](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd)
- [Canonical knowledge: Bare, Coupling-On Diagonal, and Hybridized Modes](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd)
- [Canonical knowledge: D3 Full Qubit--Readout--Filter Complex Response Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/worked-examples/d3-full-qrp-complex-response-fit.qmd)
- [Canonical knowledge: D3 Initial Reference Topologies](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/worked-examples/d3-initial-reference-topologies.qmd)
- [Canonical knowledge: Resonator Decay, Linewidth, and Quality Factor](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/resonator-decay-linewidth-and-quality-factor.qmd)

## Authority boundary

Root Knowledge owns the physics: coordinate basis, reductions, Hamiltonian,
port map, estimator eligibility, parameter layers, and promotion roles. This
Workbench contract does not restate those derivations. It owns the record that
lets a reviewer prove which canonical model a concrete artifact implemented.

In particular, a Workbench payload is not made authoritative by naming a field
`bare`, `loaded_bare`, or `final`. The artifact must show the topology and
basis that produced the value. Initializer labels map as follows:

| Runtime label | Canonical role |
| --- | --- |
| `System A` / `system_a` | $\mathcal T_{\mathrm{QR}}$ initializer |
| `System B` / `system_b` | $\mathcal T_{\mathrm{RP}}$ initializer |
| coupling off | explicitly qualified `off-ref` initializer |

The current D3 Same-Die route is owned by its host Design Target. It optimizes
physical coordinates with the direct fixed-node Hybridized Circuit and derives
its cared quantities from the complete-complement open-EOM reduction.
Equivalent-circuit records may be produced only as downstream mapped
representations that close back to that physical winner. No independent
Equivalent optimizer or structured response fit is a current D3 authority.

## Required Content

| Field | Requirement |
| --- | --- |
| model family | RLC, RLGC, coupling model, mode extraction, or another named family |
| parameters | values with explicit units and physical meaning |
| topology and basis | retained physical circuit, coordinate order, transform/reduction history, and parameter layer |
| matrices and maps | source or replay path for $\mathbf C$, $\mathbf K$, Hamiltonian, and port/direct maps when the model claims them |
| source evidence | references to the normalized S/Y/Z trace used for fitting or to the validated per-unit-length matrix artifact used directly |
| fit range | frequency range and any excluded samples |
| metrics | residual, RMSE, quality score, or another explicit fit quality measure |
| model trace | reconstructed trace for visual comparison when available |
| assumptions | topology, port convention, grounding, symmetry, and reduction assumptions |
| provenance | upstream source and analysis notebook or package version |
| promotion role | cost/final authority, validation-only, or diagnostic-only |
| implementation conformance | canonical model identifier plus every declared approximation or missing map |

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
- future quantum-model study that uses fitted circuit parameters
- future dynamics study that consumes an explicit Hamiltonian or operator artifact

The last two consumers are intended placement contracts only. The Workbench
currently has no quantum-model package and no quantum-model notebook that
executes either handoff.

For a multi-resonator Final Validation, assemble the complete distributed or
lumped Circuit Model with every resonator and the shared feedline, then inspect
its full $S/Y/Z$ response once. Keep accepted pair-extracted parameters fixed;
do not introduce a second multi-pair analytic fitter or refit each pair inside
the final model.

## Related

- [Equivalent Circuit To Quantum Model](../../workflows/equivalent-circuit-to-quantum-model/index.md)
- [Quantum Dynamics / Pulse Simulation](../../workflows/quantum-dynamics-pulse-simulation/index.md)
- [Quantum Model Boundary](quantum-model-boundary.md)
