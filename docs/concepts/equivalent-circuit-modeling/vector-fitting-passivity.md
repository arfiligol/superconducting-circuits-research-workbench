---
aliases:
 - Vector Fitting And Passivity
tags:
 - diataxis/explanation
 - audience/team
 - topic/equivalent-circuit-modeling
status: stable
owner: docs-team
audience: team
scope: Handoff from Workbench vector-fitting implementations to the canonical SCQ_Design Vector Fitting and Passivity node.
version: v1.4.0
last_updated: 2026-07-13
updated_by: codex
title: Vector Fitting And Passivity
sidebar:
 label: Vector Fitting And Passivity
 order: 40
---

# Vector Fitting And Passivity

The reusable vector-fitting and passivity explanation is owned by the
SCQ_Design knowledge base:

- [Canonical knowledge: Vector Fitting And Passivity](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/vector-fitting-passivity.qmd)

This repository owns only the concrete implementation and workflow entry
points:

- [`domain/math/s_parameters.py`](https://github.com/arfiligol/superconducting-circuits-research-workbench/blob/main/core/python/analysis/superconducting_circuits_analysis/superconducting_circuits_analysis/domain/math/s_parameters.py)
  owns the scikit-rf-backed `MultiResonanceVectorFitter` implementation.
- [`application/analysis/fitting/s_parameters.py`](https://github.com/arfiligol/superconducting-circuits-research-workbench/blob/main/core/python/analysis/superconducting_circuits_analysis/superconducting_circuits_analysis/application/analysis/fitting/s_parameters.py)
  owns validation and the `fit_complex_s21_vector` application contract.
- [`SuperconductingCircuitsAnalysisBridge.jl`](https://github.com/arfiligol/superconducting-circuits-research-workbench/blob/main/core/julia/SuperconductingCircuitsAnalysisBridge/src/SuperconductingCircuitsAnalysisBridge.jl)
  owns the Julia-to-Python bridge used by repository notebooks.

The current contract fits one scalar complex `S21` response. Its internal
one-response scikit-rf `Network` is an algebraic carrier, not a physical
one-port or a fabricated two-port. The result is labeled
`scalar_s21_vector`, records the caller's fit settings, and reports the RMS of
that scalar complex response only.

`n_resonators`, `bg_poles`, and `min_q` are required inputs. The first two set
the starting model order; `min_q` classifies the implementation's
`resonances` bucket versus low-Q fit artifacts: only `Ql > min_q` enters that
bucket, while equality remains in the artifact bucket. The bucket name does
not promote a physical parameter by itself: its entries are candidate
resonances until the consuming workflow applies convergence, aligned-residue,
continuation, ambiguity, and residual gates.

For a topology-isolated scalar response, a uniquely continued Vector Fitting
complex pole may formally own its frequency and total linewidth. The circuit
fixture and mode continuation own the physical identity; Vector Fitting owns
only the pole value. Promotion requires stable fit windows and model orders,
non-vanishing residue, no unowned nearby pole, adequate complex-response
residuals, and a denser-source-trace refinement check. In particular, a local
frequency step larger than the extracted linewidth blocks promotion even when
the fit reports a stable pole.

The current application contract records the input grid but does not implement
an automatic resolution or source-grid-refinement promotion gate. It does not
publish a per-point gate containing `frequency_step_hz`, `linewidth_hz`,
`samples_per_linewidth`, refinement levels, and pole/linewidth shifts against
declared tolerances. Callers must not relabel a successful current payload as
promoted evidence without that external evidence. Interpolating the same coarse
samples is not a refinement study.

Outside the isolated, uniquely owned case, scalar Vector Fitting remains a
diagnostic cross-check. It never owns the mode identity, $g$, $J$, a transfer
zero, or internal/external or left/right linewidth decomposition. A
topology-specific `notch_s21` fit may independently interpret the same trace
and test model agreement, but its success is not a mandatory validator of an
otherwise eligible Vector Fitting pole. The caller—and ultimately the Human
reviewer—owns the fit choices and every promotion threshold.

These entry points do not accept a complete port-labeled network and do not
implement passivity or reciprocity checking or enforcement. Do not export
their result as a connected network macromodel.

Do not duplicate vector-fitting or passivity theory here; update the canonical
page and keep only repository-specific behavior at these entry points.
