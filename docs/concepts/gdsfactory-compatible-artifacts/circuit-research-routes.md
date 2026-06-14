---
aliases:
 - Circuit Research Routes
 - Research routes
tags:
 - diataxis/explanation
 - audience/team
 - topic/research-stack
status: stable
owner: docs-team
audience: team
scope: Four-route mental model for circuit-first research in the workbench.
version: v2.0.0
last_updated: 2026-06-14
updated_by: codex
title: Circuit Research Routes
description: Explains the four circuit research routes and how reusable circuit authoring, upstream FEM results, equivalent circuits, quantum modeling, and pulse simulation fit together.
sidebar:
 label: Circuit Research Routes
 order: 20
---

# Circuit Research Routes

This workbench is circuit-first. It does not own layout authoring, mesh generation, Palace handoff, or GDSFactory ecosystem execution. Those jobs may happen upstream in GDSFactory, gsim, gplugins, qpdk, HFSS, Q3D, Palace, or another simulation environment. This repo owns circuit authoring, circuit response research, external result interpretation, equivalent-circuit handoff, and downstream quantum-model research boundaries.

## Route 1: Reusable Circuit Authoring

Route 1 starts from the circuit idea itself.

```text
Pluto Notebook
  -> Julia Core reusable component or plan builder
  -> CircuitPlan
  -> JosephsonCircuits.jl response
  -> S/Y/Z traces, sweeps, figures, and reusable package logic
```

Use this route when the research question is about designing, reusing, and simulating a circuit model inside this repo. Pluto is the first research surface. Julia Core owns the stable reusable component and plan semantics. JosephsonCircuits.jl is the frequency-domain circuit solver behind the Julia Core response path.

## Route 2: FEM Result To Equivalent Circuit

Route 2 starts from an upstream simulation result.

```text
upstream FEM/simulation result
  -> trace table, Touchstone, or normalized Zarr package
  -> S/Y/Z normalization
  -> equivalent RLC/RLGC/coupling/mode/rational fit
  -> reviewable equivalent-circuit artifact
```

Use this route when the source of evidence is a layout or FEM workflow outside this repo. The result may come from GDSFactory/gsim/gplugins/qpdk, but this repo should not import those runtimes to execute layout or FEM jobs. The compatibility target is the artifact shape and terminology: frequency axes, port labels, S/Y/Z matrices, units, provenance, fitted equivalent circuit parameters, and result packages.

## Route 3: Equivalent Circuit To Quantum Model

Route 3 starts after a reusable or fitted equivalent circuit exists.

```text
equivalent circuit parameters
  -> scqubits circuit, subsystem, or custom circuit representation
  -> Hamiltonian, spectra, matrix elements, coherence estimates
  -> operator or HilbertSpace handoff
```

Use this route when the research question is about the quantum model implied by a circuit. Python is the canonical route for scqubits-style superconducting-qubit modeling. Julia operator experiments are valid only as an isolated quantum lane, not as Julia Core responsibilities.

## Route 4: Quantum Dynamics / Pulse Simulation

Route 4 starts after a Hamiltonian or explicit operator model exists.

```text
Hamiltonian or operator model
  -> QuTiP or qutip-qip dynamics/pulse experiment
  -> time traces, gate-level pulse evidence, open-system results
  -> report or reusable future quantum package
```

Use this route when the research question is about time evolution, drives, decoherence, or pulse-level simulation. QuTiP and qutip-qip are the first Python route; QuantumToolbox.jl and QuantumOptics.jl are optional isolated Julia dynamics routes.

## How The Routes Meet

The first two routes meet at the equivalent circuit layer. A distributed circuit from Julia Core may produce S/Y/Z traces that can be reduced into an equivalent model. An upstream FEM result may be reduced into the same model family. Once the equivalent circuit is explicit, Route 3 can construct the quantum model and Route 4 can run dynamics or pulse studies.

## Quantum Modeling Position

There is no official Julia version of `scqubits` in the current public ecosystem. `scqubits` is the Python route for superconducting-qubit spectra, custom circuit YAML, matrix elements, coherence estimates, and QuTiP interop. Julia packages such as QuantumToolbox.jl or QuantumOptics.jl are valid operator/dynamics tools, but they are not replacements for the scqubits circuit-quantization layer.

The docs therefore use this rule:

| Need | Preferred route |
| --- | --- |
| reusable circuit construction and JosephsonCircuits response | Julia Core + Pluto |
| external FEM result normalization and equivalent-circuit fitting | Python Analysis Core + Python notebooks |
| scqubits-style superconducting-qubit modeling | Python notebooks or a future Python quantum package |
| pulse-level or open-system dynamics | Python notebooks with QuTiP/qutip-qip first |
| Julia-native operator or pulse/dynamics experiment | a separate Julia quantum lane, not Julia Core |

## Boundary

Julia Core must stay focused on reusable components, CircuitPlan, simulation intent, JosephsonCircuits.jl wrapping, and circuit response outputs. It must not grow dependencies on scqubits, QuTiP, QuantumToolbox.jl, QuantumOptics.jl, gdsfactory, gsim, gplugins, qpdk, PythonCall, or notebook-only analysis libraries.

## Related

- [Reusable Circuit Design](../../start/reusable-circuit-design.md)
- [External FEM Result To Equivalent Circuit](../../workflows/fem-result-to-equivalent-circuit/external-fem-result-to-equivalent-circuit.md)
- [Equivalent Circuit To Quantum Model](../../workflows/equivalent-circuit-to-quantum-model/index.md)
- [Quantum Dynamics / Pulse Simulation](../../workflows/quantum-dynamics-pulse-simulation/index.md)
- [Research Contracts](../../reference/research-contracts/index.md)
