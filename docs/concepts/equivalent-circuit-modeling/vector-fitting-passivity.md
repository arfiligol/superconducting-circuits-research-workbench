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
version: v1.2.0
last_updated: 2026-07-10
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
the starting model order; `min_q` classifies promoted resonances versus low-Q
fit artifacts: only `Ql > min_q` is promoted, while equality remains in the
artifact bucket. The caller—and ultimately the Human reviewer—owns those
choices, including the comparator. This repository must not hide a default
pole count or condition threshold.

These entry points do not accept a complete port-labeled network and do not
implement passivity or reciprocity checking or enforcement. Do not export
their result as a connected network macromodel.

Do not duplicate vector-fitting or passivity theory here; update the canonical
page and keep only repository-specific behavior at these entry points.
