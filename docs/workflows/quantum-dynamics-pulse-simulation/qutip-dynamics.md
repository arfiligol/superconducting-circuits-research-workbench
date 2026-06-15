---
aliases:
 - QuTiP Dynamics
tags:
 - diataxis/how-to
 - audience/user
 - topic/quantum-dynamics
status: draft
owner: docs-team
audience: user
scope: Python notebook workflow for QuTiP time evolution and open-system dynamics after Hamiltonian construction.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: QuTiP Dynamics
sidebar:
 label: QuTiP Dynamics
 order: 20
---

# QuTiP Dynamics

Use this workflow when Route 3 has produced an operator or Hamiltonian and the next question is time evolution, dissipation, or driven response.

## Procedure Shape

1. Start from an explicit Hamiltonian, collapse-operator set, and initial state.
2. Keep parameter provenance tied to the equivalent circuit that produced the Hamiltonian.
3. Build the QuTiP model in a Python notebook.
4. Run the time evolution or steady-state solve needed for the research question.
5. Store plots, solver settings, and input parameters with the report evidence.

## Promotion Rule

Notebook code can stay notebook-only while it explores one research question. Promote only stable, repeated helper logic into a future quantum package. Do not promote this code into Julia Core.

## References

- [QuTiP documentation](https://qutip.org/)
- [QuTiP time-dependent dynamics guide](https://qutip.readthedocs.io/en/latest/guide/dynamics/dynamics-time.html)
- [scqubits HilbertSpace guide](https://scqubits.readthedocs.io/en/v4.1/guide/hilbertspace/ipynb/hilbertspace.html)
