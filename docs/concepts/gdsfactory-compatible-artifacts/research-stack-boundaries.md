---
aliases:
 - Research Stack
 - Research Runtime Boundaries
tags:
 - diataxis/explanation
 - audience/team
 - topic/architecture
status: stable
owner: docs-team
audience: team
scope: Responsibility boundaries for the four circuit research routes.
version: v2.0.0
last_updated: 2026-06-14
updated_by: codex
title: Research Stack
sidebar:
 label: Overview
 order: 10
---

# Research Stack Boundaries

The research stack keeps fast notebook work separate from reusable package code. Pluto is the direct Julia research surface; Julia Core owns reusable circuit semantics; Python Analysis Core owns reusable fitting and matrix algorithms; future quantum modeling belongs outside Julia Core.

## Route Map

| Route | Starts from | Main surface | Package owner |
| --- | --- | --- | --- |
| Reusable Circuit Authoring | circuit idea, reusable component, plan builder | Pluto | Julia Core |
| FEM Result To Equivalent Circuit | upstream trace table, Touchstone, or Zarr package | Python Notebook and Python Analysis Core | Python Analysis Core |
| Equivalent Circuit To Quantum Model | equivalent circuit parameters | Python Notebook first | future Python quantum package if stabilized |
| Quantum Dynamics / Pulse Simulation | Hamiltonian or operator model | Python Notebook first | future quantum package if stabilized |

## Responsibility Model

| Layer | Owns | Does not own |
| --- | --- | --- |
| Pluto Notebook | research execution, sliders, figures, solver experiments, Julia Core route studies | reusable package APIs |
| Julia Core | components, systems, compiler model, simulation helpers, JosephsonCircuits.jl response wrappers | plotting libraries, Python calls, scqubits, QuTiP, gdsfactory, gsim, gplugins or qpdk |
| Julia Visualizer | PlotlyJS figure construction for Julia traces | circuit semantics |
| Analysis Bridge | explicit Pluto-to-Python analysis calls | Python algorithm ownership |
| Python Analysis Core | external-result normalization, fitting, preprocessing, matrix analysis, plain result shapes | notebook narrative, quantum package ownership, or layout/FEM execution |
| Python Notebook | file inspection, Python-native analysis sketches, scikit-rf-compatible ingestion, scqubits/QuTiP/qutip-qip exploration, report evidence | reusable package contracts or Julia simulation compute |
| Isolated quantum lane | scqubits/QuTiP helpers, qutip-qip pulse studies, or optional Julia dynamics experiments | Julia Core, product runtime, or layout/FEM runtime |

## Design Pressure

Notebook cells should stay fast to change. Package code should stay small, testable, and reusable. When the same cell logic appears in multiple studies, move the stable computation into Julia Core or Python Analysis Core and keep notebooks as evidence surfaces.

## Related

- [Reusable Circuit Authoring](../../workflows/reusable-circuit-authoring/index.md)
- [FEM Result To Equivalent Circuit](../../workflows/fem-result-to-equivalent-circuit/index.md)
- [Equivalent Circuit To Quantum Model](../../workflows/equivalent-circuit-to-quantum-model/index.md)
- [Quantum Dynamics / Pulse Simulation](../../workflows/quantum-dynamics-pulse-simulation/index.md)
- [Circuit Research Routes](circuit-research-routes.md)
