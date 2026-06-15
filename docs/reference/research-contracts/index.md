---
aliases:
 - Research Contracts
 - Circuit research contracts
tags:
 - diataxis/reference
 - audience/team
 - sot/true
 - topic/research-contracts
status: stable
owner: docs-team
audience: team
scope: Stable research-core contracts for external FEM result ingestion, equivalent circuit models, quantum model boundaries, and notebook roles.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Research Contracts
description: Contract index for the four circuit research routes.
sidebar:
 label: Overview
 order: 10
---

# Research Contracts

These contracts keep the four research routes connected without mixing implementation ownership. They define stable handoff surfaces between reusable Julia Core studies, external simulation artifacts, Python Analysis Core, notebooks, quantum-model construction, and pulse/dynamics studies.

## Page Map

| Page | Owns |
| --- | --- |
| [External FEM Result Contract](external-fem-result-contract.md) | accepted input artifact families and normalized trace semantics |
| [Equivalent Circuit Model Contract](equivalent-circuit-model-contract.md) | fitted model fields, metrics, provenance, and handoff expectations |
| [Quantum Model Boundary](quantum-model-boundary.md) | scqubits, QuTiP, qutip-qip, and isolated Julia dynamics placement rules |
| [Notebook Roles](notebook-roles.md) | Pluto and Python notebook responsibilities |

## Route Fit

| Route | Contract surface |
| --- | --- |
| Reusable Circuit Authoring | Julia Core contracts and equivalent circuit handoff where reduction is needed |
| FEM Result To Equivalent Circuit | External FEM Result Contract -> Equivalent Circuit Model Contract |
| Equivalent Circuit To Quantum Model | Equivalent Circuit Model Contract -> Quantum Model Boundary |
| Quantum Dynamics / Pulse Simulation | Quantum Model Boundary -> notebook evidence and future quantum package boundary |

## Related

- [Circuit Research Routes](../../concepts/gdsfactory-compatible-artifacts/circuit-research-routes.md)
- [FEM Result To Equivalent Circuit](../../workflows/fem-result-to-equivalent-circuit/index.md)
- [Notebook Interface](../notebooks/index.md)
